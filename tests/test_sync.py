import pytest

from bupt_rag.models import AppError, QARequest
from bupt_rag.service import KnowledgeService


def test_idempotent_and_restart(service):
    initial = service.status()
    calls = len(service.encoder.calls)
    result = service.sync()
    assert not result.changed
    assert len(service.encoder.calls) == calls
    service.close()
    restored = KnowledgeService(service.settings, service.source, service.encoder)
    assert restored.status() == initial
    assert len(restored.index.edges) == len(service.index.edges)
    restored.close()


def test_add_update_delete_and_history(service):
    original = next(iter(service.snapshot["payload"]["documents"].values()))
    old_commit = service.source.commit
    old_id = original["document"]["id"]
    path = original["document"]["source_path"]
    service.source.commit = "b" * 40
    service.source.documents[path] += "\n# 新标题\n\n新增一段独立资料。\n"
    service.source.documents["src/content/docs/学习生活/新文件.md"] = "# 新文件\n\n另一个新段落。\n"
    removed = next(p for p in service.source.documents if p != path)
    del service.source.documents[removed]
    before = len(service.encoder.calls)
    result = service.sync()
    assert (result.added, result.updated, result.deleted) == (1, 1, 1)
    assert len(service.encoder.calls) == before + 1
    assert len(service.encoder.calls[-1][0]) == 2
    assert service.get_document(old_id, old_commit)["text"] == original["text"]
    assert service.get_document(old_id)["document"]["id"] == old_id
    assert all(ev.source_commit == "b" * 40 for ev in service.index.evidence.values())


@pytest.mark.parametrize("failure", ["source", "encoder"])
def test_failed_sync_preserves_snapshot(service, failure):
    old = service.status()
    service.source.commit = "b" * 40
    service.source.documents["src/content/docs/学习生活/new.md"] = "# New\n\nSome new text."
    getattr(service, failure).fail = True
    with pytest.raises(AppError):
        service.sync()
    assert service.status() == old
    assert service.store.latest()["revision"] == old.knowledge_revision


def test_changed_paragraph_withdraws_old_edges(service):
    path = "src/content/docs/沙河校区/日常活动.md"
    service.source.documents[path] = service.source.documents[path].replace(
        "雁南和雁北均有一站式多功能厅", "已撤销：雁南和雁北均有一站式多功能厅"
    )
    service.source.commit = "c" * 40
    service.sync()
    assert not any(e.name == "沙河雁南一站式多功能厅" for e in service.index.entities.values())
    assert service.snapshot["payload"]["pending"]


def test_publication_failure_keeps_old_index(service, monkeypatch):
    old = service.status()
    service.source.commit = "c" * 40
    monkeypatch.setattr(
        service.store, "publish", lambda *args: (_ for _ in ()).throw(RuntimeError("disk full"))
    )
    with pytest.raises(RuntimeError):
        service.sync()
    assert service.status() == old


def test_model_change_requires_reindex(service):
    service.encoder.identity = "different-model:v2"
    with pytest.raises(AppError, match="Embedding"):
        service.ask(QARequest(question="图书馆"))
    result = service.sync()
    assert result.changed
    assert service.snapshot["payload"]["encoder"] == "different-model:v2"
