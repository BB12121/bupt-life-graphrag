import argparse
import json
from pathlib import Path

from .config import REFERENCE_COMMIT, Settings
from .knowledge import FactRule
from .models import AppError, QARequest
from .service import KnowledgeService


def emit(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="北邮生活指南 GraphRAG 后端管理")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="同步资料（默认复现设计文档的固定版本）")
    sync.add_argument("--ref", default=REFERENCE_COMMIT)
    sub.add_parser("status")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--campus", choices=["shahe", "haidian"])
    ask.add_argument("--mode", choices=["hybrid", "vector"], default="hybrid")
    pending = sub.add_parser("pending", help="输出待审核原文候选")
    pending.add_argument("--output", type=Path)
    review = sub.add_parser("approve", help="导入人工审核后的 FactRule JSON 数组；停服操作")
    review.add_argument("file", type=Path)
    suggest_parser = sub.add_parser("suggest", help="调用本地小模型生成候选草稿，不入图")
    suggest_parser.add_argument("candidate_id")
    suggest_parser.add_argument("--output", type=Path, required=True)
    batch = sub.add_parser("extract", help="批量规则/模型抽取，自动保存断点，不发布")
    batch.add_argument("--model", action="store_true")
    batch.add_argument("--retry-errors", action="store_true")
    batch.add_argument("--limit", type=int)
    records = sub.add_parser("drafts", help="导出带来源和审核历史的抽取记录")
    records.add_argument("--output", type=Path, required=True)
    decide = sub.add_parser("review", help="审核草稿；批准后仍需 sync 发布")
    decide.add_argument("record_id")
    decide.add_argument("decision", choices=["approved", "rejected", "text_only"])
    decide.add_argument("--reviewer", required=True)
    decide.add_argument("--reason", required=True)
    decide.add_argument("--corrections", type=Path)
    args = parser.parse_args()
    service = KnowledgeService(Settings())
    try:
        if args.command == "sync":
            emit(service.sync(args.ref))
        elif args.command == "status":
            emit(service.status())
        elif args.command == "extract":
            from .extraction import batch_extract

            if args.limit is not None and args.limit < 1:
                raise AppError("invalid_request", "limit 必须大于零。", 422)
            emit(batch_extract(service, args.model, args.retry_errors, args.limit))
        elif args.command == "drafts":
            from .extraction import export_records

            export_records(service.store, args.output)
            emit({"output": str(args.output)})
        elif args.command == "review":
            from .extraction import review_record

            service.require_ready()
            corrections = (
                json.loads(args.corrections.read_text(encoding="utf-8")) if args.corrections else None
            )
            emit(
                review_record(service, args.record_id, args.decision, args.reviewer, args.reason, corrections)
            )
        elif args.command == "ask":
            emit(service.ask(QARequest(question=args.question, campus=args.campus, mode=args.mode)))
        elif args.command == "pending":
            service.require_ready()
            records = service.snapshot["payload"]["pending"]
            if args.output:
                args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                emit(records)
        elif args.command == "approve":
            service.require_ready()
            rules = [FactRule.model_validate(x) for x in json.loads(args.file.read_text(encoding="utf-8"))]
            documents = service.snapshot["payload"]["documents"]
            for rule in rules:
                record = documents.get(rule.source_path)
                if not record or not any(
                    c["text"] == rule.quote and c["heading"] == rule.heading for c in record["chunks"]
                ):
                    raise AppError("invalid_review", "审核事实的整段引文和标题必须匹配当前原文。", 422)
            target = service.settings.data_dir / "reviewed_facts.json"
            old = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
            merged = old + [r.model_dump() for r in rules]
            merged = list({json.dumps(r, sort_keys=True, ensure_ascii=False): r for r in merged}.values())
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(target)
            emit({"approved": len(rules), "next": "重新执行 sync 发布新知识版本，然后启动 API。"})
        elif args.command == "suggest":
            from .llm import suggest_many

            service.require_ready()
            candidate = next(
                (c for c in service.snapshot["payload"]["pending"] if c["id"] == args.candidate_id), None
            )
            if candidate is None:
                raise AppError("candidate_not_found", "候选 ID 不存在。", 404)
            draft = suggest_many(candidate, service.settings)
            args.output.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            emit({"draft_file": str(args.output), "requires_human_review": True})
    except AppError as exc:
        emit({"error": {"code": exc.code, "message": exc.message}})
        raise SystemExit(1) from exc
    finally:
        service.close()


if __name__ == "__main__":
    main()
