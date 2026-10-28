"""Resumable draft extraction. Nothing in this module publishes facts."""

import json
import re
from datetime import datetime, timezone

from .knowledge import FactRule
from .models import AppError
from .parsing import stable_id

VERSION = "rules-model-v1"


def rule_drafts(candidate):
    """Recognize explicit simple sentences, leaving complex semantics to review."""
    text = candidate["quote"]
    if re.search(r"不|未|无|除|或|若|如果|仅|只有|才能", text):
        return []
    name = r"([\w\u4e00-\u9fff·（）()]{2,40})"
    patterns = [
        (name + "位于" + name, "Place", "LOCATED_IN", "Place"),
        (name + "提供" + name + "服务", "Place", "PROVIDES", "Service"),
        (name + "通过" + name + "办理", "Service", "USES_PLATFORM", "Platform"),
        (name + "需要" + name, "Service", "REQUIRES", "Condition"),
    ]
    drafts = []
    for sentence in re.split(r"[。；\n]", text):
        for pattern, left, relation, right in patterns:
            match = re.fullmatch(pattern, sentence.strip())
            if not match:
                continue
            if relation == "LOCATED_IN" and match[2] in {"沙河校区", "海淀校区"}:
                right = "Campus"

            def entity(value, kind):
                return {"name": value, "type": kind, "campus": candidate.get("campus", "unknown")}

            drafts.append(
                FactRule.model_validate(
                    {
                        "source_path": candidate["source_path"],
                        "heading": candidate["heading"],
                        "quote": text,
                        "subject": entity(match[1], left),
                        "relation": relation,
                        "object": entity(match[2], right),
                    }
                ).model_dump()
            )
    return drafts


def batch_extract(service, use_model=False, retry_errors=False, limit=None):
    from .llm import suggest_many

    service.require_ready()
    settings = service.settings
    profile = stable_id(
        VERSION,
        str(use_model),
        settings.llm_base_url if use_model else "",
        settings.llm_model if use_model else "",
    )
    processed = skipped = errors = 0
    for candidate in service.snapshot["payload"]["pending"]:
        key = stable_id(candidate["id"], candidate["source_commit"], profile)
        old = service.store.extraction_record(key)
        if old and not (old["status"] == "error" and retry_errors):
            skipped += 1
            continue
        if limit is not None and processed >= limit:
            break
        record = {
            "id": key,
            "candidate": candidate,
            "profile": profile,
            "model": settings.llm_model if use_model else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "history": [],
        }
        try:
            drafts = rule_drafts(candidate)
            method = "rules"
            if not drafts and use_model:
                drafts = suggest_many(candidate, settings)
                method = "model"
            record.update(status="pending_review", drafts=drafts, method=method)
        except AppError as exc:
            record.update(status="error", drafts=[], error=exc.code)
            errors += 1
        service.store.save_extraction(record)
        processed += 1
    return {"processed": processed, "skipped": skipped, "errors": errors, "requires_human_review": True}


def review_record(service, record_id, decision, reviewer, reason, corrections=None):
    if not reviewer.strip() or not reason.strip():
        raise AppError("invalid_review", "审核人和依据不能为空。", 422)
    record = service.store.extraction_record(record_id)
    if record is None:
        raise AppError("candidate_not_found", "抽取记录不存在。", 404)
    if decision not in {"approved", "rejected", "text_only"}:
        raise AppError("invalid_review", "不支持的审核结论。", 422)
    candidate = record["candidate"]
    if candidate["source_commit"] != service.snapshot["commit_sha"]:
        raise AppError("stale_review", "资料版本已变化，请重新抽取并审核。", 422)
    document = service.snapshot["payload"]["documents"].get(candidate["source_path"])
    if not document or not any(
        c["text"] == candidate["quote"] and c["heading"] == candidate["heading"] for c in document["chunks"]
    ):
        raise AppError("stale_review", "原文已失效。", 422)
    drafts = record["drafts"] if corrections is None else corrections
    if decision == "approved":
        if not drafts:
            raise AppError("invalid_review", "空候选不能批准，请标记仅保留文本。", 422)
        drafts = [FactRule.model_validate(d).model_dump() for d in drafts]
        for draft in drafts:
            if any(draft[k] != candidate[k] for k in ("source_path", "heading", "quote")):
                raise AppError("invalid_review", "修正事实不能改变来源定位或完整证据。", 422)
    record["history"].append(
        {
            "decision": decision,
            "reviewer": reviewer,
            "reason": reason,
            "previous_drafts": record["drafts"],
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    record.update(status=decision, drafts=drafts)
    service.store.save_extraction(record)
    return record


def approved_rules(store):
    return [
        FactRule.model_validate(d)
        for record in store.extraction_records()
        if record["status"] == "approved"
        for d in record["drafts"]
    ]


def export_records(store, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(store.extraction_records(), ensure_ascii=False, indent=2), encoding="utf-8")
