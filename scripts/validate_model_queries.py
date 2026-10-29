"""Live smoke cases frozen before execution; not an independent human benchmark."""

import hashlib
import json
from pathlib import Path

from bupt_rag.llm import suggest_many
from bupt_rag.models import AppError, QARequest
from bupt_rag.service import KnowledgeService

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("no_relation", "今天的心情很好。"),
    ("negation", "星光大厅不提供证件打印服务。"),
    ("alternative", "证件补办需要携带身份证或输入身份证号，二者任选其一。"),
    ("stage", "研讨间预约无需两人到场；实际使用研讨间时必须至少两人打卡。"),
    ("multiple", "星光大厅提供证件打印服务。证件打印通过星光平台办理。"),
]
QUERIES = [
    ("two_hop", "劳动教育学时查询的平台需要什么条件？", None, "answered", 2),
    ("reverse", "海淀图书馆自助打印在哪里？", "haidian", "answered", 1),
    ("intersection", "课表查询和成绩查询有什么共同平台？", None, "answered", 1),
    ("missing_path", "海淀图书馆二楼的服务通过什么平台？", "haidian", "abstained", 0),
    ("unseen_1", "想查劳动教育学时，劳动教育学时查询的渠道有什么前提？", None, "answered", 2),
    ("unseen_2", "海淀图书馆自助打印要带什么呢？", "haidian", "answered", 1),
    ("unseen_3", "课表查询与成绩查询都能通过哪个网站办？", None, "answered", 1),
    ("unseen_4", "请问海淀图书馆自助打印在何处办理？", "haidian", "answered", 1),
]


def main():
    service = KnowledgeService()
    result = {
        "source_commit": service.snapshot["commit_sha"],
        "model": service.settings.llm_model,
        "qa_sha256": hashlib.sha256((ROOT / "bupt_rag/qa.py").read_bytes()).hexdigest(),
        "method": "Cases written after template freeze, no tuning; same-author smoke verification, not blind evaluation",
        "model_cases": [],
        "query_cases": [],
    }
    before = service.status()
    try:
        for name, quote in CASES:
            candidate = {
                "id": name,
                "source_path": "synthetic/model-validation.md",
                "heading": name,
                "quote": quote,
                "campus": "shared",
                "source_commit": "synthetic",
                "line_start": 1,
                "line_end": 1,
            }
            try:
                drafts = suggest_many(candidate, service.settings)
                result["model_cases"].append({"case": name, "input": candidate, "drafts": drafts})
            except AppError as exc:
                result["model_cases"].append({"case": name, "input": candidate, "error": exc.code})
        for name, question, campus, status, hops in QUERIES:
            response = service.ask(QARequest(question=question, campus=campus))
            passed = response.status == status and (
                not hops or any(len(p.edges) == hops for p in response.paths)
            )
            if name in {"intersection", "unseen_3"}:
                passed = passed and {p.branch_id for p in response.paths} == {0, 1}
            result["query_cases"].append(
                {
                    "case": name,
                    "question": question,
                    "passed": passed,
                    "expected_status": status,
                    "expected_hops": hops,
                    "response": response.model_dump(),
                }
            )
        result["no_publication"] = service.status() == before
        (ROOT / "docs/model-query-validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "model_cases": len(result["model_cases"]),
                    "queries_passed": sum(r["passed"] for r in result["query_cases"]),
                    "no_publication": result["no_publication"],
                }
            )
        )
    finally:
        service.close()


if __name__ == "__main__":
    main()
