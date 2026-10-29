import copy
import json
import threading

from filelock import FileLock, Timeout

from .config import REPOSITORY, Settings
from .embedding import BGEEncoder
from .knowledge import extract, extract_glossary, load_glossary, load_rules
from .models import AppError, KnowledgeStatus, SyncResponse
from .parsing import chunks, document, stable_id
from .qa import answer
from .retrieval import Index, build_part
from .source import GitHubSource
from .storage import Store


class KnowledgeService:
    def __init__(self, settings=None, source=None, encoder=None):
        self.settings = settings or Settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.process_lock = FileLock(self.settings.data_dir / "backend.lock")
        try:
            self.process_lock.acquire(timeout=0)
        except Timeout as exc:
            raise AppError(
                "knowledge_in_use", "此数据目录正被另一后端或 CLI 占用；请使用单进程并停服后运行管理命令。"
            ) from exc
        self.store = Store(self.settings.data_dir)
        self.source = source or GitHubSource()
        self.encoder = encoder or BGEEncoder(self.settings)
        self.lock = threading.RLock()
        self.snapshot = self.store.latest()
        self.index = Index(self.snapshot["payload"]) if self.snapshot else None
        self.last_sync_stats = None

    def close(self):
        if hasattr(self.source, "close"):
            self.source.close()
        self.process_lock.release()

    def require_ready(self):
        if self.snapshot is None:
            raise AppError("knowledge_not_initialized", "尚未导入资料，请先调用知识同步接口。")
        if self.snapshot["payload"]["encoder"] != self.encoder.identity:
            raise AppError("model_mismatch", "Embedding 配置已变化，请重新同步构建索引。")

    def status(self):
        s = self.snapshot
        return KnowledgeStatus(
            repository=REPOSITORY,
            source_commit=s["commit_sha"] if s else None,
            knowledge_revision=s["revision"] if s else 0,
            document_count=len(s["payload"]["documents"]) if s else 0,
            last_synced_at=s["created_at"] if s else None,
        )

    def sync(self, ref="main"):
        with self.lock:
            from .extraction import approved_rules

            rules = load_rules(self.settings.data_dir) + approved_rules(self.store)
            glossary = load_glossary()
            rule_key = stable_id(
                json.dumps([r.model_dump() for r in rules] + glossary, sort_keys=True, ensure_ascii=False)
            )
            # config_key covers everything (no-op detection); parse_key alone decides chunk reuse.
            config_key = stable_id("parser-v5-all-paragraphs", self.encoder.identity, rule_key)
            parse_key = stable_id("parser-v5-all-paragraphs", self.encoder.identity)
            by_path = {}
            for item in [r.model_dump() for r in rules] + glossary:
                by_path.setdefault(item["source_path"], []).append(item)
            commit = self.source.resolve(ref)
            old = self.snapshot
            if old and old["commit_sha"] == commit and old["config_key"] == config_key:
                self.last_sync_stats = {"index": "unchanged"}
                return SyncResponse(
                    source_commit=commit,
                    knowledge_revision=old["revision"],
                    added=0,
                    updated=0,
                    deleted=0,
                    pending_count=len(old["payload"]["pending"]),
                    changed=False,
                )
            files = self.source.fetch(commit)
            if not files:
                raise AppError("incomplete_source", "空快照不发布；请检查上游正文清单。")
            previous = old["payload"]["documents"] if old else {}
            same_parse = old is not None and old["payload"].get("parse_key") == parse_key
            cached = self.store.cached_vectors(self.encoder.identity)
            documents, pending = {}, []
            to_encode = {}
            stats = {"parsed": 0, "extracted": 0, "relabeled": 0, "reused": 0}
            changed_paths = set()
            for path, text in sorted(files.items()):
                content_hash = stable_id(text)
                extract_key = stable_id(json.dumps(by_path.get(path, []), sort_keys=True, ensure_ascii=False))
                prev = previous.get(path) if same_parse else None
                if prev and prev["content_hash"] == content_hash:
                    record = copy.deepcopy(prev)
                    record["document"] = document(path, text, commit).model_dump()
                    if prev.get("extract_key") != extract_key:
                        # Only this document's rules changed: keep its chunks, redo extraction.
                        facts, candidates = extract(path, record["chunks"], rules)
                        record.update(
                            facts=facts,
                            pending=candidates,
                            entities=extract_glossary(path, record["chunks"], glossary),
                            extract_key=extract_key,
                        )
                        stats["extracted"] += 1
                        changed_paths.add(path)
                    elif prev["document"]["source_commit"] != commit:
                        stats["relabeled"] += 1
                        changed_paths.add(path)
                    else:
                        stats["reused"] += 1
                else:
                    pieces = chunks(path, text, self.encoder.token_length)
                    facts, candidates = extract(path, pieces, rules)
                    record = {
                        "document": document(path, text, commit).model_dump(),
                        "text": text,
                        "content_hash": content_hash,
                        "extract_key": extract_key,
                        "chunks": pieces,
                        "facts": facts,
                        "pending": candidates,
                        "entities": extract_glossary(path, pieces, glossary),
                    }
                    stats["parsed"] += 1
                    changed_paths.add(path)
                for c in record["chunks"]:
                    # Include the heading in embeddings to distinguish anonymous time/price paragraphs.
                    embedded_text = c["heading"] + "\n" + c["text"]
                    if self.encoder.token_length(embedded_text) > 500:
                        embedded_text = c["text"]
                    vector_key = stable_id(embedded_text)
                    c["vector_key"] = vector_key
                    if vector_key not in cached:
                        to_encode[vector_key] = embedded_text
                documents[path] = record
                pending.extend({**c, "source_commit": commit} for c in record["pending"])
            new_vectors = {}
            if to_encode:
                keys = list(to_encode)
                vectors = self.encoder.encode([to_encode[k] for k in keys])
                if len(vectors) != len(keys):
                    raise AppError("model_unavailable", "模型返回向量数与片段数不符。")
                import numpy as np

                if vectors.ndim != 2 or not np.isfinite(vectors).all():
                    raise AppError("model_unavailable", "模型返回无效向量。")
                new_vectors = {key: value.tolist() for key, value in zip(keys, vectors)}
            cached.update(new_vectors)
            for record in documents.values():
                for c in record["chunks"]:
                    c["vector"] = cached[c["vector_key"]]
            payload = {
                "documents": documents,
                "pending": pending,
                "encoder": self.encoder.identity,
                "parse_key": parse_key,
            }
            removed = previous.keys() - files.keys()
            stats["removed"] = len(removed)
            # Everything that can fail (parsing, tokenizing, encoding) is finished before publication.
            if same_parse and self.index is not None:
                parts = {p: build_part(documents[p], self.index.parts.get(p)) for p in changed_paths}
                index = None
            else:
                index = Index(payload)
            published = self.store.publish(commit, config_key, payload, self.encoder.identity, new_vectors)
            if index is None:
                try:
                    self.index.apply(parts, removed)
                    stats["index"] = "delta"
                except Exception:
                    # Keep memory consistent with the published snapshot.
                    self.index = Index(payload)
                    stats["index"] = "full_fallback"
            else:
                self.index = index
                stats["index"] = "full"
            self.snapshot, self.last_sync_stats = published, stats
            return SyncResponse(
                source_commit=commit,
                knowledge_revision=published["revision"],
                added=len(files.keys() - previous.keys()),
                deleted=len(previous.keys() - files.keys()),
                updated=sum(
                    previous[p]["content_hash"] != documents[p]["content_hash"]
                    for p in files.keys() & previous.keys()
                ),
                pending_count=len(pending),
                changed=True,
            )

    def ask(self, request):
        with self.lock:
            self.require_ready()
            return answer(request, self.snapshot, self.index, self.encoder, self.settings)

    def get_document(self, doc_id, commit=None):
        if commit:
            record = self.store.historical_document(doc_id, commit)
        else:
            records = self.snapshot["payload"]["documents"].values() if self.snapshot else []
            record = next((r for r in records if r["document"]["id"] == doc_id), None)
        if record is None:
            raise AppError("document_not_found", "文档或已保存的资料版本不存在。", 404)
        return {"document": record["document"], "text": record["text"]}
