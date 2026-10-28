from conftest import TestEncoder
from fastapi.testclient import TestClient

from bupt_rag.api import create_app
from bupt_rag.config import Settings
from bupt_rag.service import KnowledgeService


def test_routes_and_errors(service):
    with TestClient(create_app(service.settings, service)) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/v1/knowledge/status").json()["document_count"] > 0
        docs = client.get("/api/v1/documents").json()["items"]
        assert client.get("/api/v1/documents/" + docs[0]["id"]).status_code == 200
        response = client.post("/api/v1/qa", json={"question": "今天图书馆开放吗"})
        assert response.status_code == 200
        assert response.json()["status"] == "abstained"
        for body in (
            {"question": " "},
            {"question": "hi", "mode": "bad"},
            {"question": "hi", "campus": "shared"},
        ):
            r = client.post("/api/v1/qa", json=body)
            assert r.status_code == 422
            assert set(r.json()) == {"error"}
        assert client.get("/api/v1/documents/missing").status_code == 404
        assert "error" in client.get("/missing").json()
        assert (
            client.post(
                "/api/v1/qa", json={"question": "test", "entity_bindings": {"test": "missing"}}
            ).status_code
            == 422
        )
        entities = client.get("/api/v1/entities", params={"campus": "shahe"}).json()["items"]
        assert all(e["campus"] in {"shahe", "shared"} for e in entities)
        spec = client.get("/openapi.json").json()
        assert "QAResponse" in spec["components"]["schemas"]


def test_not_initialized(tmp_path, source):
    service = KnowledgeService(Settings(data_dir=tmp_path), source, TestEncoder())
    with TestClient(create_app(service.settings, service)) as client:
        assert client.get("/api/v1/knowledge/status").json()["source_commit"] is None
        assert client.get("/api/v1/documents").json() == {"items": []}
        assert client.post("/api/v1/qa", json={"question": "图书馆"}).status_code == 503


def test_admin_key(service):
    service.settings.admin_key = "test-only-key"
    with TestClient(create_app(service.settings, service)) as client:
        assert client.post("/api/v1/knowledge/sync", json={}).status_code == 401
        assert (
            client.post(
                "/api/v1/knowledge/sync", json={}, headers={"X-Admin-Key": "test-only-key"}
            ).status_code
            == 200
        )
