import json

import numpy as np
import pytest

from bupt_rag import retrieval
from bupt_rag.knowledge import FactRule, load_rules
from bupt_rag.models import QARequest
from bupt_rag.retrieval import Index

NEW_PATH = "src/content/docs/沙河校区/增量测试.md"
NEW_QUOTE = "星光大厅提供证件打印服务。"


def new_rule():
    return FactRule(
        source_path=NEW_PATH,
        heading="增量测试",
        quote=NEW_QUOTE,
        subject={"name": "星光大厅", "type": "Place", "campus": "shahe"},
        relation="PROVIDES",
        object={"name": "证件打印", "type": "Service", "campus": "shahe"},
    )


def write_reviewed(service, rules):
    path = service.settings.data_dir / "reviewed_facts.json"
    path.write_text(json.dumps([r.model_dump() for r in rules], ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def tokenized(monkeypatch):
    texts = []
    original = retrieval.tokenize

    def counting(text):
        texts.append(text)
        return original(text)

    monkeypatch.setattr(retrieval, "tokenize", counting)
    return texts


def assert_matches_full_rebuild(service):
    live, full = service.index, Index(service.snapshot["payload"])
    assert [c["evidence_id"] for c in live.chunks] == [c["evidence_id"] for c in full.chunks]
    assert np.array_equal(live.vectors, full.vectors)
    assert live.tokens == full.tokens and live.df == full.df
    assert live.lengths.tolist() == full.lengths.tolist() and live.avg_len == full.avg_len
    assert {k: e.evidence_ids for k, e in live.edges.items()} == {
        k: e.evidence_ids for k, e in full.edges.items()
    }
    assert set(live.graph.edges(keys=True)) == set(full.graph.edges(keys=True))
    assert set(live.graph.nodes) == set(full.graph.nodes)
    assert list(live.entities.items()) == list(full.entities.items())
    assert live.evidence == full.evidence and live.conflict_evidence == full.conflict_evidence


def test_new_rule_reextracts_only_its_document(service, tokenized):
    service.source.documents[NEW_PATH] = f"# 增量测试\n\n{NEW_QUOTE}\n"
    service.source.commit = "b" * 40
    service.sync()
    encoded, tokenized_before = len(service.encoder.calls), len(tokenized)
    write_reviewed(service, [new_rule()])
    result = service.sync()
    stats = service.last_sync_stats
    assert result.changed and stats["index"] == "delta"
    assert (stats["parsed"], stats["extracted"], stats["relabeled"]) == (0, 1, 0)
    assert len(service.encoder.calls) == encoded and len(tokenized) == tokenized_before
    answer = service.ask(QARequest(question="星光大厅提供什么服务？", campus="shahe"))
    assert answer.status == "answered" and "证件打印" in answer.answers[0].text
    assert_matches_full_rebuild(service)


def test_edited_document_tokenizes_only_new_paragraphs(service, tokenized):
    path = next(iter(service.source.documents))
    service.source.documents[path] += "\n# 新标题\n\n新增一段独立资料。\n"
    service.source.commit = "b" * 40
    service.sync()
    stats = service.last_sync_stats
    assert stats["parsed"] == 1 and stats["index"] == "delta"
    assert stats["relabeled"] == len(service.source.documents) - 1
    assert tokenized == ["新标题 新增一段独立资料。"]
    assert_matches_full_rebuild(service)


def test_commit_only_change_relabels_without_reprocessing(service, tokenized):
    encoded = len(service.encoder.calls)
    service.source.commit = "b" * 40
    service.sync()
    stats = service.last_sync_stats
    assert stats["relabeled"] == len(service.source.documents)
    assert stats["parsed"] == stats["extracted"] == 0
    assert tokenized == [] and len(service.encoder.calls) == encoded
    assert all(ev.source_commit == "b" * 40 for ev in service.index.evidence.values())
    assert all(
        e in service.index.evidence for edge in service.index.edges.values() for e in edge.evidence_ids
    )
    assert_matches_full_rebuild(service)


def test_delta_sequence_matches_full_rebuild(service, monkeypatch):
    rules = load_rules(service.settings.data_dir)
    duplicate = rules[0].model_copy(update={"source_path": "src/content/docs/学习生活/duplicate.md"})
    conflicting = [
        rules[0].model_copy(update={"conflict_key": "test-exclusive", "decision": "one"}),
        rules[1].model_copy(update={"conflict_key": "test-exclusive", "decision": "two"}),
    ]
    steps = [
        lambda docs: docs.update({NEW_PATH: f"# 增量测试\n\n{NEW_QUOTE}\n"}),
        lambda docs: docs.update({duplicate.source_path: f"# {duplicate.heading}\n\n{duplicate.quote}\n"}),
        lambda docs: docs.pop(next(p for p in sorted(docs) if p != duplicate.source_path)),
        lambda docs: docs.pop(duplicate.source_path),
    ]
    monkeypatch.setattr("bupt_rag.service.load_rules", lambda _: rules + [duplicate])
    for i, step in enumerate(steps):
        step(service.source.documents)
        service.source.commit = str(i + 1) * 40
        service.sync()
        assert service.last_sync_stats["index"] == "delta"
        assert_matches_full_rebuild(service)
    monkeypatch.setattr("bupt_rag.service.load_rules", lambda _: conflicting + rules[2:])
    service.sync()
    assert service.index.conflict_evidence
    assert_matches_full_rebuild(service)


def test_failed_delta_falls_back_to_full_rebuild(service, monkeypatch):
    live = service.index

    def broken(upserts, removed):
        live.parts.clear()  # leave the live index half-updated
        raise RuntimeError("simulated failure")

    service.source.commit = "b" * 40
    monkeypatch.setattr(live, "apply", broken)
    result = service.sync()
    assert service.index is not live
    assert result.changed and service.last_sync_stats["index"] == "full_fallback"
    assert service.index.parts
    assert_matches_full_rebuild(service)
