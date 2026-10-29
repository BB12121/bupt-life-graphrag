import json

import httpx
import pytest

from bupt_rag.config import Settings
from bupt_rag.llm import OUTPUT_SCHEMA, suggest_many
from bupt_rag.models import AppError

CANDIDATE = {
    "id": "c1",
    "source_path": "src/content/docs/沙河校区/测试.md",
    "heading": "测试 / 打印",
    "quote": "星光大厅提供证件打印服务。",
    "campus": "shahe",
    "line_start": 3,
    "line_end": 3,
}
FACT = {
    "subject": {"name": "星光大厅", "type": "Place", "campus": "shahe"},
    "relation": "PROVIDES",
    "object": {"name": "证件打印", "type": "Service", "campus": "shahe"},
}


@pytest.fixture
def reply(monkeypatch):
    sent = {}

    def install(content):
        def post(self, url, headers=None, json=None):
            sent.update(url=url, headers=headers, body=json)
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"choices": [{"message": {"content": content}}]},
            )

        monkeypatch.setattr(httpx.Client, "post", post)
        return sent

    return install


def local(tmp_path):
    return Settings(data_dir=tmp_path, llm_base_url="http://127.0.0.1:8080/v1", llm_model="qwen2.5-1.5b")


def test_local_request_is_schema_constrained_few_shot(tmp_path, reply):
    sent = reply(json.dumps({"facts": [FACT]}))
    drafts = suggest_many(CANDIDATE, local(tmp_path))
    body = sent["body"]
    assert body["response_format"]["json_schema"]["schema"] == OUTPUT_SCHEMA
    assert "enable_thinking" not in body
    roles = [m["role"] for m in body["messages"]]
    assert roles[0] == "system" and roles.count("assistant") >= 2 and roles[-1] == "user"
    # Only the paragraph itself is sent; ids and line numbers stay local.
    assert json.loads(body["messages"][-1]["content"]) == {
        "heading": CANDIDATE["heading"],
        "quote": CANDIDATE["quote"],
        "campus": "shahe",
    }
    assert len(drafts) == 1
    assert drafts[0]["quote"] == CANDIDATE["quote"] and drafts[0]["subject"]["aliases"] == []


def test_remote_request_keeps_provider_options(tmp_path, reply):
    sent = reply(json.dumps([FACT]))
    settings = Settings(data_dir=tmp_path, llm_base_url="https://llm.example.com/v1", llm_api_key="test-key")
    assert len(suggest_many(CANDIDATE, settings)) == 1
    assert "response_format" not in sent["body"] and sent["body"]["enable_thinking"] is False


@pytest.mark.parametrize(
    "content",
    [
        "```json\n" + json.dumps({"facts": [FACT]}, ensure_ascii=False) + "\n```",
        json.dumps(FACT, ensure_ascii=False),
        json.dumps([FACT, FACT], ensure_ascii=False),
    ],
)
def test_tolerated_output_shapes(tmp_path, reply, content):
    reply(content)
    assert len(suggest_many(CANDIDATE, local(tmp_path))) == 1


def test_invalid_and_invented_items_are_dropped(tmp_path, reply):
    wrong_direction = {**FACT, "relation": "USES_PLATFORM"}
    invented = {
        **FACT,
        "subject": {"name": "月光广场", "type": "Place", "campus": "shahe"},
        "object": {"name": "复印", "type": "Service", "campus": "shahe"},
    }
    reply(json.dumps({"facts": [wrong_direction, invented, FACT]}, ensure_ascii=False))
    drafts = suggest_many(CANDIDATE, local(tmp_path))
    assert [(d["subject"]["name"], d["relation"]) for d in drafts] == [("星光大厅", "PROVIDES")]


def test_no_relation_is_not_an_error(tmp_path, reply):
    reply('{"facts": []}')
    assert suggest_many(CANDIDATE, local(tmp_path)) == []


def test_only_invalid_items_is_an_error(tmp_path, reply):
    reply(json.dumps({"facts": [{**FACT, "relation": "USES_PLATFORM"}]}))
    with pytest.raises(AppError, match="模型"):
        suggest_many(CANDIDATE, local(tmp_path))
