import math
import re
from collections import Counter

import networkx as nx
import numpy as np

from .models import Edge, Entity, GraphPath
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
        for s in re.findall(r"[\u4e00-\u9fff]+", text)
        for i in range(len(s) - 1)
        if s[i : i + 2] not in STOP
    ]
    return base + bigrams


def scope_matches(scope, campus):
    return scope != "unknown" and (campus is None or scope in {campus, "shared"})


class Index:
    def __init__(self, payload):
        self.chunks, self.evidence, self.entities, self.edges = [], {}, {}, {}
        self.graph = nx.MultiDiGraph()
        self.conflicts = {}
        for record in payload["documents"].values():
            for item in record.get("entities", []):
                entity = Entity.model_validate(item)
                self.entities[entity.id] = entity
            from .models import Document

            doc = Document.model_validate(record["document"])
            by_key = {}
            for chunk in record["chunks"]:
                ev = evidence_for(doc, chunk)
                self.evidence[ev.id] = ev
                item = {**chunk, "evidence_id": ev.id}
                self.chunks.append(item)
                by_key[chunk["key"]] = ev.id
            for fact in record["facts"]:
                sub, obj = Entity.model_validate(fact["subject"]), Entity.model_validate(fact["object"])
                self.entities[sub.id], self.entities[obj.id] = sub, obj
                key = (sub.id, fact["relation"], obj.id)
                if key not in self.edges:
                    self.edges[key] = Edge(
                        subject_id=sub.id, relation=fact["relation"], object_id=obj.id, evidence_ids=[]
                    )
                eid = by_key[fact["chunk_key"]]
                if eid not in self.edges[key].evidence_ids:
                    self.edges[key].evidence_ids.append(eid)
                if fact.get("conflict_key"):
                    self.conflicts.setdefault(fact["conflict_key"], {}).setdefault(
                        fact["decision"], set()
                    ).add(eid)
        for key, edge in self.edges.items():
            self.graph.add_edge(edge.subject_id, edge.object_id, key=key[1], edge=edge)
        self.conflict_evidence = set()
        for decisions in self.conflicts.values():
            if len(decisions) > 1:
                self.conflict_evidence.update(e for ids in decisions.values() for e in ids)
        self.tokens = [Counter(tokenize(c["heading"] + " " + c["text"])) for c in self.chunks]
        self.lengths = np.array([sum(t.values()) for t in self.tokens])
        self.avg_len = float(self.lengths.mean()) if len(self.lengths) else 1
        self.df = Counter(t for counts in self.tokens for t in counts)
        self.vectors = np.asarray([c["vector"] for c in self.chunks], dtype=np.float32)

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
            for u, v, _, data in candidates:
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
