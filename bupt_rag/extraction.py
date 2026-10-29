"""Resumable draft extraction. Nothing in this module publishes facts."""

import json
import re
from datetime import datetime, timezone

from .knowledge import FactRule
from .models import AppError
from .parsing import stable_id

VERSION = "rules-model-v2"

# A sentence with negation, exceptions, alternatives or conditions is left entirely to review.
HEDGED = re.compile(r"不|未|无|除|或|若|如果|如需|如有|仅|只有|才能|禁止|暂停|取消|违约")
NAME = r"[\w一-鿿·（）()、 ]{2,30}?"
PLACE = re.compile(r"(楼|层|侧|厅|馆|室|园|中心|校区|食堂|餐厅|超市|广场|门|路|区|站|处|间|内)$")
PLATFORM = re.compile(r"系统|平台|网上服务大厅|小程序|App|APP|app|公众号|门户|网站|企业微信|微信|邮箱")
ACTION = r"预约|办理|申请|报修|查询|签到|注册|缴费|充值|报名|登记"
CAMPUSES = {"沙河校区", "海淀校区"}


def plain(text):
    """Markdown emphasis, links, footnotes and list markers removed; wording kept."""
    text = re.sub(r"\[\^[\w-]+\]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", text)
    return text.replace("**", "").replace("`", "").strip()


def clean_name(value):
    value = (value or "").strip(" 「」“”\"'").removesuffix("时")
    value = re.sub(r"(均|都|也|同样)$", "", value).strip()
    return value if 2 <= len(value) <= 30 and not value.isdigit() else ""


def clean_subject(value):
    """Reject clause openers ("但可以", "作为新生") that regexes capture as subjects."""
    value = re.sub(r"(当日|当天)$", "", clean_name(value))
    return (
        ""
        if re.match(r"但|是|作为|可以|可|需要|需|须|如|而|并|且|则|就|也|还|即|通过|在", value)
        else clean_name(value)
    )


def quoted_platform(sentence):
    for inner in re.findall(r"「([^」]+)」", sentence):
        name = clean_name(inner.split("->")[0])
        if name:
            return name
    match = re.search(rf"(?:通过|在|使用)\s*({NAME})\s*(?:中|上|内|进行|{ACTION})", sentence)
    if match and PLATFORM.search(match[1]):
        return clean_name(match[1])
    return ""


def sentence_relations(sentence, label, fallback):
    """Yield ((name, type), relation, (name, type)) for one explicit, unhedged sentence."""
    if label:
        # "- **报修**：……通过「北邮接诉即办」进行报修": the list label names the service.
        platform = quoted_platform(sentence)
        if platform:
            yield (label, "Service"), "USES_PLATFORM", (platform, "Platform")
    for clause in re.split(r"[，,]", sentence):
        clause = clause.strip()
        located = re.fullmatch(rf"({NAME})?位于\s*({NAME})", clause)
        if located:
            # A heading naming an activity ("医疗报销") is not a place that can be located.
            heading_place = "" if re.search(ACTION + "|报销|服务", fallback) else fallback
            subject, place = clean_subject(located[1]) or heading_place, clean_name(located[2])
            if subject[:4] in CAMPUSES:
                continue
            if subject and place and subject != place and (place in CAMPUSES or PLACE.search(place)):
                yield (subject, "Place"), "LOCATED_IN", (place, "Campus" if place in CAMPUSES else "Place")
            continue
        provides = re.fullmatch(rf"({NAME})提供({NAME})服务", clause)
        if provides and clean_subject(provides[1]) and clean_name(provides[2]):
            yield (clean_subject(provides[1]), "Place"), "PROVIDES", (clean_name(provides[2]), "Service")
            continue
        via = re.fullmatch(
            rf"({NAME})?(?:可以|可|均可|也可以|需要|需|须)?(?:通过|在)\s*({NAME})\s*(?:中|上|内)?(?:进行)?({ACTION})([\w一-鿿]{{0,8}})",
            clause,
        )
        if via and PLATFORM.search(via[2] or ""):
            # "迎新系统的本科生学号" is a phrase around a platform, not its name.
            subject, platform = clean_subject(via[1]), "" if "的" in via[2] else clean_name(via[2])
            action = via[3] + via[4]
            owner = subject or fallback
            if owner and PLACE.search(owner):
                # A place booked on a platform: Place -> its booking service -> Platform.
                service = clean_name(owner + action)
                if service:
                    yield (owner, "Place"), "PROVIDES", (service, "Service")
            else:
                service = clean_name((subject or (fallback if not via[4] else "")) + action)
            if service and platform:
                yield (service, "Service"), "USES_PLATFORM", (platform, "Platform")
            continue
        requires = re.fullmatch(
            rf"({NAME})?(?:同样|也|均|都)?(?:需要|需|须|必须)((?:携带|持有|连接)\s*{NAME})", clause
        )
        if requires:
            subject = clean_subject(requires[1]) or fallback
            condition = clean_name(requires[2])
            # Conditions attach to a service or platform; a place subject ("研讨间") needs review.
            if subject and condition and not PLACE.search(subject):
                kind = "Platform" if PLATFORM.search(subject) else "Service"
                yield (subject, kind), "REQUIRES", (condition, "Condition")


def rule_drafts(candidate):
    """Recognize explicit sentences one by one; complex semantics are left to review."""
    text = candidate["quote"]
    fallback = clean_name(candidate.get("heading", "").split(" / ")[-1])
    campus = candidate.get("campus", "unknown")
    drafts = []
    for line in text.split("\n"):
        labelled = re.match(r"^\s*(?:[-*+]\s+)?\*\*([^*]{2,15})\*\*\s*[：:](.*)$", line)
        label = clean_name(labelled[1]) if labelled else ""
        body = plain(labelled[2] if labelled else line)
        for sentence in re.split(r"[。；！？]", body):
            sentence = sentence.strip()
            if not sentence or HEDGED.search(sentence):
                continue
            for (left, left_type), relation, (right, right_type) in sentence_relations(
                sentence, label, fallback
            ):

                def entity(name, kind):
                    return {"name": name, "type": kind, "campus": "shared" if kind == "Platform" else campus}

                try:
                    draft = FactRule.model_validate(
                        {
                            "source_path": candidate["source_path"],
                            "heading": candidate["heading"],
                            "quote": text,
                            "subject": entity(left, left_type),
                            "relation": relation,
                            "object": entity(right, right_type),
                        }
                    ).model_dump()
                except ValueError:
                    continue
                if draft not in drafts:
                    drafts.append(draft)
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
