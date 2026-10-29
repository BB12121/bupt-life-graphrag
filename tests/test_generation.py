import threading

import httpx
import pytest

from bupt_rag.generation import check, sentences
from bupt_rag.models import Evidence, QARequest

QUESTION = "劳动教育学时查询的平台需要什么条件？"


def evidence(n, quote, heading="测试"):
    return Evidence(
        id=f"e{n}",
        doc_id="d",
        source_commit="a" * 40,
        source_path="p.md",
        heading=heading,
        line_start=1,
        line_end=1,
        quote=quote,
        source_url="https://example.com",
    )


EVIDENCE = [evidence(1, "图书馆开放时间 8:00-22:00。"), evidence(2, "研讨间需在图书馆系统预约。")]


def test_citation_after_terminator_belongs_to_previous_sentence():
    assert sentences("图书馆 8:00 开门。[1]研讨间要预约。[2]") == [
        "图书馆 8:00 开门。[1]",
        "研讨间要预约。[2]",
    ]


@pytest.mark.parametrize(
    "text, cited",
    [
        ("图书馆 8:00 开门 [1]，研讨间需在图书馆系统预约 [2]。", ["e1", "e2"]),
        ("研讨间需要预约。[2][1]", ["e2", "e1"]),
        # Short connective fragments do not need their own citation.
        ("研讨间需在图书馆系统预约 [2]。好的。", ["e2"]),
        ("图书馆提供以下服务：\n研讨间预约 [2]。\n开放时间 8:00-22:00 [1]。", ["e2", "e1"]),
    ],
)
def test_grounded_answers_pass(text, cited):
    assert check(text, EVIDENCE) == cited


@pytest.mark.parametrize(
    "text",
    [
        "图书馆 8:00 开门 [1]。研讨间可以随便使用。",  # uncited sentence
        "研讨间需要预约 [3]。",  # citation outside the evidence list
        "8:00 以后可以办理以下业务：\n研讨间预约 [2]。",  # a lead-in with a number still needs a source
        "研讨间可以随便用：\n",  # a lead-in with nothing cited after it
        "图书馆 7:30 开门 [1]。",  # number not in the cited source
        "研讨间 22:00 关门 [2]。",  # number only in another, uncited source
        "",
        "研讨间需在图书馆系统预约 [2]。" * 60,  # too long
    ],
)
def test_ungrounded_answers_fall_back(text):
    assert check(text, EVIDENCE) is None


@pytest.fixture
def model(service, monkeypatch):
    service.settings.answer_base_url = "http://127.0.0.1:8080/v1"
    sent = {"reply": None, "calls": 0}

    def post(self, url, headers=None, json=None):
        sent["calls"] += 1
        sent["body"] = json
        # Answer generation must not hold the knowledge lock.
        acquired = []

        def probe():
            acquired.append(service.lock.acquire(timeout=1))
            if acquired[0]:
                service.lock.release()

        worker = threading.Thread(target=probe)
        worker.start()
        worker.join()
        sent["lock_free"] = acquired[0]
        if sent["reply"] is None:
            raise httpx.ConnectError("simulated")
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": sent["reply"]}}]},
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    return sent


def test_generated_answer_is_added_without_changing_the_response(service, model):
    plain = service.ask(QARequest(question=QUESTION, generate=False))
    assert plain.status == "answered" and plain.generated is None and model["calls"] == 0
    model["reply"] = "需要满足原文所列条件 [1]。"
    response = service.ask(QARequest(question=QUESTION))
    assert model["lock_free"]
    assert response.generated.text == "需要满足原文所列条件 [1]。"
    assert response.generated.evidence_ids == [response.evidence[0].id]
    assert response.generated.model == service.settings.answer_model
    assert response.model_dump(exclude={"generated"}) == plain.model_dump(exclude={"generated"})
    user = model["body"]["messages"][-1]["content"]
    assert QUESTION in user and "[1] " + response.evidence[0].heading in user


@pytest.mark.parametrize("reply", [None, "原文没有写到的内容。", "需要满足条件 [9]。"])
def test_model_failure_or_ungrounded_reply_keeps_excerpts(service, model, reply):
    model["reply"] = reply
    response = service.ask(QARequest(question=QUESTION))
    assert response.status == "answered" and response.answers and response.generated is None


def test_no_generation_for_abstained_or_when_unconfigured(service, model):
    model["reply"] = "随便说说 [1]。"
    assert service.ask(QARequest(question="今天食堂开门吗？")).generated is None
    service.settings.answer_base_url = ""
    assert service.ask(QARequest(question=QUESTION)).generated is None
    assert model["calls"] == 0
