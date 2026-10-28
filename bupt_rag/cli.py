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
    args = parser.parse_args()
    service = KnowledgeService(Settings())
    try:
        if args.command == "sync":
            emit(service.sync(args.ref))
        elif args.command == "status":
            emit(service.status())
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
            from .llm import suggest

            service.require_ready()
            candidate = next(
                (c for c in service.snapshot["payload"]["pending"] if c["id"] == args.candidate_id), None
            )
            if candidate is None:
                raise AppError("candidate_not_found", "候选 ID 不存在。", 404)
            draft = suggest(candidate, service.settings)
            args.output.write_text(
                json.dumps([draft] if draft else [], ensure_ascii=False, indent=2), encoding="utf-8"
            )
            emit({"draft_file": str(args.output), "requires_human_review": True})
    except AppError as exc:
        emit({"error": {"code": exc.code, "message": exc.message}})
        raise SystemExit(1) from exc
    finally:
        service.close()


if __name__ == "__main__":
    main()
