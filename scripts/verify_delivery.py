"""Live integration smoke check; not an answer-quality benchmark."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from bupt_rag.api import create_app
from bupt_rag.config import Settings
from bupt_rag.models import QARequest
from bupt_rag.service import KnowledgeService

settings = Settings()
service = KnowledgeService(settings)
results = []
for question in ["劳动教育学时查询的平台需要什么条件？", "体育运动达标成绩查询的平台需要什么条件？"]:
    result = service.ask(QARequest(question=question))
    assert result.status == "answered", result
    assert any(len(p.edges) == 2 for p in result.paths)
    assert len({e.source_path for e in result.evidence}) >= 2
    results.append({"question": question, "response": result.model_dump()})
with TestClient(create_app(settings, service)) as client:
    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/knowledge/status").json()["document_count"] == 39
Path("docs/live-smoke.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Real BGE, two new cross-document paths, API health and built frontend: passed")
