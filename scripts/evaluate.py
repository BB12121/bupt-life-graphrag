"""Run the SAME snapshot/model/context budget for hybrid and vector retrieval.

Keyword checks are a reproducible proxy, never a substitute for human answer grading.
"""

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

import psutil

from bupt_rag.config import Settings
from bupt_rag.models import QARequest
from bupt_rag.service import KnowledgeService


def evidence_complete(case, response):
    for needed in case["required_evidence"]:
        if not any(
            e.source_path == needed["source_path"]
            and e.source_commit == needed["source_commit"]
            and e.line_start <= needed["line_start"]
            and e.line_end >= needed["line_end"]
            and needed["quote"] in e.quote
            for e in response.evidence
        ):
            return False
    return bool(response.answers)


def graph_proof_complete(case, response):
    if not case["min_hops"]:
        return None
    if not any(len(p.edges) >= case["min_hops"] for p in response.paths):
        return False
    if case["category"] == "intersection" and {p.branch_id for p in response.paths} != {0, 1}:
        return False
    return evidence_complete(case, response)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("evaluation/questions.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results.json"))
    args = parser.parse_args()
    gold = json.loads(args.questions.read_text(encoding="utf-8"))
    svc = KnowledgeService(Settings())
    process = psutil.Process()
    rows, summaries = [], {}
    try:
        svc.require_ready()
        if svc.snapshot["commit_sha"] != gold["source_commit"]:
            raise SystemExit("评测快照不匹配；请同步题库指定提交后重试。")
        # Warm up once, identically for both modes. Startup/cold load is not query latency.
        svc.encoder.encode(["模型预热"], query=True)
        for mode in ("hybrid", "vector"):
            for case in gold["cases"]:
                start = time.perf_counter()
                response = svc.ask(QARequest(**case["request"], mode=mode))
                elapsed = time.perf_counter() - start
                text = "\n".join(a.text for a in response.answers)
                status_match = (
                    response.status == case["expected_status"] and response.reason == case["expected_reason"]
                )
                proxy = status_match and all(word in text for word in case["answer_keywords"])
                rows.append(
                    {
                        "id": case["id"],
                        "mode": mode,
                        "category": case["category"],
                        "expected_status": case["expected_status"],
                        "keyword_correct_proxy": proxy,
                        "complete_evidence_chain": evidence_complete(case, response),
                        "complete_graph_proof": graph_proof_complete(case, response),
                        "latency_seconds": elapsed,
                        "rss_bytes": process.memory_info().rss,
                        "human_correct": None,
                        "response": response.model_dump(),
                    }
                )
            group = [r for r in rows if r["mode"] == mode]
            answerable = [r for r in group if r["expected_status"] == "answered"]
            abstentions = [r for r in group if r["expected_status"] == "abstained"]
            summaries[mode] = {
                "questions": len(group),
                "keyword_correct_proxy": sum(r["keyword_correct_proxy"] for r in group) / len(group),
                "human_answer_accuracy": None,
                "complete_evidence_chain_rate": sum(r["complete_evidence_chain"] for r in answerable)
                / len(answerable),
                "unanswerable_abstention_rate": sum(
                    r["response"]["status"] == "abstained" for r in abstentions
                )
                / len(abstentions),
                "median_latency_seconds": statistics.median(r["latency_seconds"] for r in group),
                "max_observed_rss_bytes": max(r["rss_bytes"] for r in group),
            }
        output = {
            "source_commit": gold["source_commit"],
            "knowledge_revision": svc.snapshot["revision"],
            "encoder": svc.encoder.identity,
            "context_chars": svc.settings.context_chars,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "process_peak_rss_bytes": getattr(process.memory_info(), "peak_wset", None),
            "limitations": [
                "keyword_correct_proxy is not human answer accuracy",
                "RSS is sampled after queries, not guaranteed peak memory",
                "complete_evidence_chain_rate compares required source coverage equally; graph proof is a separate metric",
            ],
            "summary": summaries,
            "rows": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
    finally:
        svc.close()


if __name__ == "__main__":
    run()
