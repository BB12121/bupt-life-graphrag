import json
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from threading import Event

import pytest

from bupt_rag.knowledge import FactRule, load_rules
from bupt_rag.models import AppError, QARequest
from bupt_rag.service import KnowledgeService


def test_shared_fact_survives_one_source_deletion(service, monkeypatch):
    rules = load_rules(service.settings.data_dir)
    duplicate = rules[0].model_copy(update={"source_path": "src/content/docs/学习生活/duplicate.md"})
    monkeypatch.setattr("bupt_rag.service.load_rules", lambda _: rules + [duplicate])
    service.source.documents[duplicate.source_path] = f"# {duplicate.heading}\n\n{duplicate.quote}\n"
    service.source.commit = "b" * 40
    service.sync()
    key = (duplicate.subject.entity().id, duplicate.relation, duplicate.object.entity().id)
    assert len(service.index.edges[key].evidence_ids) == 2
    del service.source.documents[duplicate.source_path]
    service.source.commit = "c" * 40
    service.sync()
    assert len(service.index.edges[key].evidence_ids) == 1


def test_conflicting_review_decisions_detected(service, monkeypatch):
    rules = load_rules(service.settings.data_dir)
    first = rules[0].model_copy(update={"conflict_key": "test-exclusive-service", "decision": "one"})
    second = rules[1].model_copy(update={"conflict_key": "test-exclusive-service", "decision": "two"})
    monkeypatch.setattr("bupt_rag.service.load_rules", lambda _: [first, second, *rules[2:]])
    service.sync()
    response = service.ask(QARequest(question="雁南一站式多功能厅通过什么平台预约？", campus="shahe"))
    assert response.status == "partial"
    assert response.reason == "conflicting_evidence"
    assert response.answers == []


def test_second_process_owner_is_rejected(service):
    with pytest.raises(AppError, match="单进程"):
        KnowledgeService(service.settings, service.source, service.encoder)


def test_query_waits_for_sync_publication(service, monkeypatch):
    started, release = Event(), Event()
    original = service.source.fetch

    def slow_fetch(commit):
        started.set()
        assert release.wait(timeout=5)
        return original(commit)

    service.source.commit = "d" * 40
    monkeypatch.setattr(service.source, "fetch", slow_fetch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        sync = pool.submit(service.sync)
        assert started.wait(timeout=5)
        qa = pool.submit(service.ask, QARequest(question="今天开放吗？"))
        assert not qa.done()
        release.set()
        revision = sync.result().knowledge_revision
        assert qa.result().knowledge_revision == revision


def test_ambiguous_card_and_binding_validation(service):
    response = service.ask(QARequest(question="校园卡是什么？"))
    assert response.status == "needs_clarification"
    assert response.reason == "ambiguous_entity"
    assert len(response.clarifications[0].options) == 2
    option = response.clarifications[0].options[0]
    bound = service.ask(QARequest(question="校园卡是什么？", entity_bindings={"校园卡": option.value}))
    assert bound.status != "needs_clarification"
    with pytest.raises(AppError):
        service.ask(QARequest(question="校园卡是什么？", entity_bindings={"校园卡": "nonexistent"}))


def test_review_rejects_illegal_relation_types():
    rule = json.loads(files("bupt_rag.resources").joinpath("facts.json").read_text(encoding="utf-8"))[0]
    rule["relation"] = "REQUIRES"
    with pytest.raises(ValueError):
        FactRule.model_validate(rule)
