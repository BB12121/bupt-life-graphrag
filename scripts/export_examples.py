from pathlib import Path

from bupt_rag.models import QARequest
from bupt_rag.service import KnowledgeService

target = Path(__file__).resolve().parents[1] / "docs/examples"
target.mkdir(exist_ok=True)
svc = KnowledgeService()
try:
    questions = {
        "answered": QARequest(question="雁南一站式多功能厅的预约平台还能办理哪些手续？", campus="shahe"),
        "needs_clarification": QARequest(question="校园卡是什么？"),
        "abstained": QARequest(question="今天图书馆开放吗？", campus="shahe"),
    }
    for name, request in questions.items():
        result = svc.ask(request)
        assert result.status == name
        (target / f"{name}.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    svc.settings.max_paths = 1  # Explicit test fixture: intentionally exhaust search capacity.
    result = svc.ask(questions["answered"])
    assert result.status == "partial"
    (target / "partial.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
finally:
    svc.close()
