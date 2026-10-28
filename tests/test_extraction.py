import pytest

from bupt_rag.extraction import batch_extract, review_record, rule_drafts
from bupt_rag.models import AppError, QARequest


def add_new(service):
    path = "src/content/docs/沙河校区/新服务.md"
    service.source.documents[path] = "# 新业务\n\n星光大厅提供证件打印服务。\n"
    service.source.commit = "f" * 40
    service.sync()
    return path


def test_new_fact_review_publish_withdraw(service):
    path = add_new(service)
    batch_extract(service)
    record = next(r for r in service.store.extraction_records() if r["candidate"]["source_path"] == path)
    assert record["drafts"][0]["object"]["name"] == "证件打印"
    assert not any(e.name == "星光大厅" for e in service.index.entities.values())
    review_record(service, record["id"], "approved", "test reviewer", "合成夹具原文明确提供关系")
    service.sync()
    response = service.ask(QARequest(question="星光大厅提供什么服务？", campus="shahe"))
    assert response.status == "answered"
    assert any("证件打印" in a.text for a in response.answers)
    service.source.documents[path] = "# 新业务\n\n星光大厅不再提供证件打印服务。\n"
    service.source.commit = "e" * 40
    service.sync()
    assert not any(e.name == "星光大厅" for e in service.index.entities.values())


def test_resume_and_review_rejection(service):
    add_new(service)
    first = batch_extract(service)
    assert first["processed"] > 0
    assert batch_extract(service)["processed"] == 0
    record = service.store.extraction_records()[0]
    review_record(service, record["id"], "rejected", "reviewer", "语义不确定")
    assert service.store.extraction_record(record["id"])["status"] == "rejected"
    assert batch_extract(service)["processed"] == 0


def test_stale_review(service):
    add_new(service)
    batch_extract(service)
    record = service.store.extraction_records()[0]
    service.source.commit = "d" * 40
    service.sync()
    with pytest.raises(AppError, match="版本"):
        review_record(service, record["id"], "approved", "reviewer", "checked")


@pytest.mark.parametrize(
    "text", ["大厅不提供打印服务。", "打印需要身份证或学生证。", "如果预约成功才能使用。"]
)
def test_complex_rules_do_not_invent_edges(text):
    assert rule_drafts({"quote": text}) == []


def test_model_error_resumes_only_explicitly(service, monkeypatch):
    add_new(service)
    calls = []

    def fail(candidate, settings):
        calls.append(candidate)
        raise AppError("llm_unavailable", "failure")

    monkeypatch.setattr("bupt_rag.llm.suggest_many", fail)
    assert batch_extract(service, use_model=True)["errors"] > 0
    count = len(calls)
    assert batch_extract(service, use_model=True)["processed"] == 0
    assert len(calls) == count
    assert batch_extract(service, use_model=True, retry_errors=True)["errors"] > 0
