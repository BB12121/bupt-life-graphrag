import httpx
import pytest

from bupt_rag.llm import suggest_many
from bupt_rag.models import AppError, QARequest


@pytest.mark.parametrize("failure", ["timeout", "offline", "json", "shape"])
def test_model_failure_preserves_answers(service, monkeypatch, failure):
    service.settings.llm_base_url = "http://127.0.0.1:8080/v1"
    before = service.status()

    def post(*args, **kwargs):
        if failure == "timeout":
            raise httpx.ReadTimeout("simulated")
        if failure == "offline":
            raise httpx.ConnectError("simulated")
        content = "invalid JSON" if failure == "json" else "[42]"
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://localhost"),
            json={"choices": [{"message": {"content": content}}]},
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    candidate = {"source_path": "fixture.md", "heading": "fixture", "quote": "fixture"}
    with pytest.raises(AppError) as caught:
        suggest_many(candidate, service.settings)
    assert caught.value.code == "llm_unavailable"
    assert service.status() == before
    assert service.ask(QARequest(question="劳动教育学时查询的平台需要什么条件？")).status == "answered"
