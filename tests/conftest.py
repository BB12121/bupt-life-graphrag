import json
from importlib.resources import files

import numpy as np
import pytest

from bupt_rag.config import Settings
from bupt_rag.service import KnowledgeService


class MemorySource:
    def __init__(self, documents):
        self.documents = documents
        self.commit = "a" * 40
        self.fail = False

    def resolve(self, ref):
        return self.commit

    def fetch(self, commit):
        if self.fail:
            from bupt_rag.models import AppError

            raise AppError("source_unavailable", "fixture failure")
        return dict(self.documents)


class TestEncoder:
    """Test double for lifecycle/invariants only; never used in benchmark results."""

    __test__ = False
    identity = "test-encoder:v1"

    def __init__(self):
        self.calls = []
        self.fail = False

    def token_length(self, text):
        return len(text)

    def encode(self, texts, query=False):
        if self.fail:
            from bupt_rag.models import AppError

            raise AppError("model_unavailable", "fixture failure")
        self.calls.append((list(texts), query))
        return np.tile(np.array([1.0, 0.0, 0.0]), (len(texts), 1))


def reference_source():
    rules = json.loads(files("bupt_rag.resources").joinpath("facts.json").read_text(encoding="utf-8"))
    rules += json.loads(files("bupt_rag.resources").joinpath("entities.json").read_text(encoding="utf-8"))
    docs, seen = {}, set()
    for rule in rules:
        key = (rule["source_path"], rule["heading"], rule["quote"])
        if key in seen:
            continue
        seen.add(key)
        docs.setdefault(rule["source_path"], "---\ntitle: 测试正文\n---\n\n")
        docs[rule["source_path"]] += f"# {rule['heading']}\n\n{rule['quote']}\n\n"
    return MemorySource(docs)


@pytest.fixture
def source():
    return reference_source()


@pytest.fixture
def service(tmp_path, source):
    svc = KnowledgeService(Settings(data_dir=tmp_path), source, TestEncoder())
    svc.sync()
    yield svc
    svc.close()
