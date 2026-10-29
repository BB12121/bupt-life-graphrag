import math
import re
from collections import Counter
from dataclasses import dataclass

import networkx as nx
import numpy as np

from .models import Document, Edge, Entity, GraphPath
from .parsing import evidence_for, stable_id

STOP = set(
    "的 了 是 在 有 和 与 及 什么 哪些 怎么 如何 哪里 请问 可以 能够 是否 需要 通过 办理 一个 哪个".split()
)


def tokenize(text):
    import jieba

    # Retain names alongside Chinese bigrams for robust partial campus names.
    base = [x.lower() for x in jieba.lcut(text) if x.strip() and x not in STOP and re.search(r"\w", x)]
    bigrams = [
        s[i : i + 2]
        for s in re.findall(r"[一-鿿]+", text)
        for i in range(len(s) - 1)
        if s[i : i + 2] not in STOP
    ]
    return base + bigrams


def scope_matches(scope, campus):
    return scope != "unknown" and (campus is None or scope in {campus, "shared"})


@dataclass(frozen=True)
class DocPart:
    """One document's contribution to the index. Tokenization happens only while building parts."""

    chunks: list
    evidence: dict
    tokens: list
    vectors: np.ndarray
    entities: dict
    facts: list  # (edge key, evidence id), deduplicated, in fact order
    conflicts: list  # (conflict key, decision, evidence id)


def build_part(record, previous=None):
    """Build a part; token counts of unchanged paragraphs are reused from the previous part."""
    doc = Document.model_validate(record["document"])
    reusable = {}
    if previous is not None:
        reusable = {(c["heading"], c["text"]): t for c, t in zip(previous.chunks, previous.tokens)}
    chunks, evidence, tokens, by_key = [], {}, [], {}
    for chunk in record["chunks"]:
        ev = evidence_for(doc, chunk)
        evidence[ev.id] = ev
        chunks.append({**chunk, "evidence_id": ev.id})
        by_key[chunk["key"]] = ev.id
        counts = reusable.get((chunk["heading"], chunk["text"]))
        tokens.append(
            counts if counts is not None else Counter(tokenize(chunk["heading"] + " " + chunk["text"]))
        )
    entities, facts, conflicts = {}, [], []
    for item in record.get("entities", []):
        entity = Entity.model_validate(item)
        entities[entity.id] = entity
    for fact in record["facts"]:
        sub, obj = Entity.model_validate(fact["subject"]), Entity.model_validate(fact["object"])
        entities[sub.id], entities[obj.id] = sub, obj
        contribution = ((sub.id, fact["relation"], obj.id), by_key[fact["chunk_key"]])
        if contribution not in facts:
            facts.append(contribution)
        if fact.get("conflict_key"):
            conflicts.append((fact["conflict_key"], fact["decision"], contribution[1]))
    vectors = np.asarray([c["vector"] for c in chunks], dtype=np.float32)
    return DocPart(chunks, evidence, tokens, vectors, entities, facts, conflicts)


class Index:
    def __init__(self, payload):
        self.parts = {}
        self.df = Counter()
        self.edge_sources = {}  # edge key -> {source path: [evidence ids]}
        self.edges = {}
        self.graph = nx.MultiDiGraph()
        self.apply({path: build_part(record) for path, record in payload["documents"].items()}, set())

    def apply(self, upserts, removed):
        """Replace or withdraw whole documents, touching only their terms and relations."""
        touched = set()
        for path in removed | upserts.keys():
            old = self.parts.pop(path, None)
            if old is None:
                continue
            for counts in old.tokens:
                self.df.subtract(counts.keys())
            for key, _ in old.facts:
                self.edge_sources[key].pop(path, None)
                touched.add(key)
        for path, part in upserts.items():
            self.parts[path] = part
            for counts in part.tokens:
                self.df.update(counts.keys())
            for key, eid in part.facts:
                self.edge_sources.setdefault(key, {}).setdefault(path, []).append(eid)
                touched.add(key)
        self.df = +self.df  # drop terms no paragraph contains any more
        self.parts = dict(sorted(self.parts.items()))
        for key in touched:
            self._refresh_edge(key)
        self._assemble()

    def _refresh_edge(self, key):
        subject, relation, obj = key
        sources = {path: ids for path, ids in self.edge_sources.get(key, {}).items() if ids}
        if not sources:
            # A relation disappears only when no remaining document supports it.
            self.edge_sources.pop(key, None)
            if self.edges.pop(key, None) is not None:
                self.graph.remove_edge(subject, obj, key=relation)
                for node in (subject, obj):
                    if node in self.graph and self.graph.degree(node) == 0:
                        self.graph.remove_node(node)
            return
        self.edge_sources[key] = sources
        ids = list(dict.fromkeys(eid for path in sorted(sources) for eid in sources[path]))
        edge = Edge(subject_id=subject, relation=relation, object_id=obj, evidence_ids=ids)
        self.edges[key] = edge
        self.graph.add_edge(subject, obj, key=relation, edge=edge)

    def _assemble(self):
        """Merge the per-document parts in path order; no parsing, tokenizing or encoding."""
        self.chunks, self.tokens, self.evidence, self.entities = [], [], {}, {}
        self.conflicts = {}
        for part in self.parts.values():
            self.chunks.extend(part.chunks)
            self.tokens.extend(part.tokens)
            self.evidence.update(part.evidence)
            # Later documents override an entity's details but keep its first position.
            self.entities.update(part.entities)
            for conflict_key, decision, eid in part.conflicts:
                self.conflicts.setdefault(conflict_key, {}).setdefault(decision, set()).add(eid)
        self.conflict_evidence = set()
        for decisions in self.conflicts.values():
            if len(decisions) > 1:
                self.conflict_evidence.update(e for ids in decisions.values() for e in ids)
        self.lengths = np.array([sum(t.values()) for t in self.tokens])
        self.avg_len = float(self.lengths.mean()) if len(self.lengths) else 1
        blocks = [part.vectors for part in self.parts.values() if len(part.chunks)]
        self.vectors = np.concatenate(blocks) if blocks else np.asarray([], dtype=np.float32)

    def retrieve(self, question, campus, encoder, mode, top=10):
        if not self.chunks:
            return []
        query = encoder.encode([question], query=True)[0]
        vector_scores = self.vectors @ query
        eligible = [i for i, c in enumerate(self.chunks) if scope_matches(c["campus"], campus)]
        dense = sorted(eligible, key=lambda i: (-float(vector_scores[i]), i))[:top]
        if mode == "vector":
            return [(self.chunks[i], float(vector_scores[i])) for i in dense]
        scores = {}
        for i in eligible:
            score = 0
            for word in set(tokenize(question)):
                frequency = self.tokens[i].get(word, 0)
                if not frequency:
                    continue
                idf = math.log(1 + (len(self.chunks) - self.df[word] + 0.5) / (self.df[word] + 0.5))
                score += (
                    idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * self.lengths[i] / self.avg_len))
                )
            scores[i] = score
        lexical = sorted((i for i in eligible if scores[i] > 0), key=lambda i: (-scores[i], i))[:top]
        rrf = Counter()
        for ranking in (dense, lexical):
            for rank, i in enumerate(ranking, 1):
                rrf[i] += 1 / (60 + rank)
        ranking = sorted(rrf, key=lambda i: (-rrf[i], i))[:top]
        return [(self.chunks[i], float(vector_scores[i])) for i in ranking]

    def walk(self, start, steps, campus, budget, branch_id=0):
        """Relation-constrained traversal; canonical edges retained on reverse walks."""
        paths = []

        def visit(nodes, edges, depth):
            if depth == len(steps):
                if budget["paths"] >= budget["max_paths"]:
                    budget["truncated"] = True
                    return
                budget["paths"] += 1
                paths.append(
                    GraphPath(
                        id=stable_id(str(branch_id), *nodes, *(e.relation for e in edges)),
                        branch_id=branch_id,
                        nodes=[self.entities[n] for n in nodes],
                        edges=edges,
                    )
                )
                return
            relation, direction = steps[depth]
            current = nodes[-1]
            candidates = (
                self.graph.out_edges(current, data=True, keys=True)
                if direction == "out"
                else self.graph.in_edges(current, data=True, keys=True)
            )
            # Sorted so path order does not depend on the order edges were added.
            for u, v, _, data in sorted(
                candidates, key=lambda c: (c[2], c[1] if direction == "out" else c[0])
            ):
                if budget["expansions"] >= budget["max_expansions"]:
                    budget["truncated"] = True
                    return
                budget["expansions"] += 1
                edge = data["edge"]
                dest = v if direction == "out" else u
                if edge.relation != relation or dest in nodes:
                    continue
                if not scope_matches(self.entities[dest].campus, campus):
                    continue
                if not edge.evidence_ids or any(e not in self.evidence for e in edge.evidence_ids):
                    continue
                visit(nodes + [dest], edges + [edge], depth + 1)

        if start in self.graph and 1 <= len(steps) <= 3:
            visit([start], [], 0)
        return paths
