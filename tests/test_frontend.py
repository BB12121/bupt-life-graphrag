from fastapi.testclient import TestClient

from bupt_rag.api import create_app


def test_built_frontend_routes_keep_api_and_assets_separate(service, tmp_path):
    dist = tmp_path / "frontend"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<html><div id="app">Vue app</div></html>', encoding="utf-8")
    (dist / "assets/app.js").write_text('console.log("app")', encoding="utf-8")
    service.settings.frontend_dist = dist
    with TestClient(create_app(service.settings, service)) as client:
        for path in ("/", "/documents", "/documents/stable-id", "/knowledge", "/lab"):
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
            assert 'id="app"' in response.text
            assert response.headers["cache-control"] == "no-cache"
        assert client.head("/documents/stable-id").status_code == 200
        assert client.get("/assets/app.js").headers["content-type"].split(";")[0] in {
            "text/javascript",
            "application/javascript",
        }
        for path in ("/assets/missing.js", "/api/v1/missing", "/unknown-route", "/documents/../../secrets"):
            response = client.get(path)
            assert response.status_code == 404
            assert "error" in response.json()
        assert client.get("/docs").status_code == 200
        assert client.get("/api/v1/documents").json()["items"]


def test_api_runs_without_a_frontend_build(service, tmp_path):
    service.settings.frontend_dist = tmp_path / "not-built"
    with TestClient(create_app(service.settings, service)) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/v1/knowledge/status").status_code == 200
