"""Conservative, source-anchored extraction and candidate review records."""

import json
from importlib.resources import files

from pydantic import Field, model_validator

from .models import Campus, Entity, EntityType, Relation, StrictModel
from .parsing import stable_id

ALLOWED = {
    "LOCATED_IN": ({"Place"}, {"Place", "Campus"}),
    "PROVIDES": ({"Place"}, {"Service"}),
    "USES_PLATFORM": ({"Service"}, {"Platform"}),
    "REQUIRES": ({"Service", "Platform"}, {"Condition"}),
}


class EntitySpec(StrictModel):
    name: str = Field(min_length=1)
    type: EntityType
    campus: Campus
    aliases: list[str] = Field(default_factory=list)
    url: str | None = None

    def entity(self):
        return Entity(id=stable_id(self.type, self.campus, self.name, self.url or ""), **self.model_dump())


class FactRule(StrictModel):
    source_path: str
    heading: str
    quote: str = Field(min_length=1)
    subject: EntitySpec
    relation: Relation
    object: EntitySpec
    # Explicit human-reviewed conflict groups (e.g. competing mutually exclusive requirements).
    conflict_key: str | None = None
    decision: str | None = None

    @model_validator(mode="after")
    def type_check(self):
        left, right = ALLOWED[self.relation]
        if self.subject.type not in left or self.object.type not in right:
            raise ValueError("relation has incompatible entity types")
        if self.subject.campus in {"shahe", "haidian"} and self.object.campus in {"shahe", "haidian"}:
            if self.subject.campus != self.object.campus:
                raise ValueError("cross-campus facts require a separate reviewed representation")
        if self.conflict_key and not self.decision:
            raise ValueError("conflict_key requires decision")
        return self


def load_rules(data_dir):
    builtin = json.loads(files("bupt_rag.resources").joinpath("facts.json").read_text(encoding="utf-8"))
    custom = data_dir / "reviewed_facts.json"
    extra = json.loads(custom.read_text(encoding="utf-8")) if custom.exists() else []
    return [FactRule.model_validate(x) for x in builtin + extra]


def load_glossary():
    return json.loads(files("bupt_rag.resources").joinpath("entities.json").read_text(encoding="utf-8"))


def extract_glossary(path, chunks, glossary):
    return [
        EntitySpec.model_validate(r["entity"]).entity().model_dump()
        for r in glossary
        if r["source_path"] == path
        and any(c["text"] == r["quote"] and c["heading"] == r["heading"] for c in chunks)
    ]


def extract(path, chunks, rules):
    facts, pending, covered = [], [], set()
    for rule in rules:
        if rule.source_path != path:
            continue
        matches = [c for c in chunks if c["heading"] == rule.heading and c["text"] == rule.quote]
        # Exact entire paragraph plus heading: edited or negated facts are withdrawn.
        for c in matches:
            subject, obj = rule.subject.entity(), rule.object.entity()
            facts.append(
                {
                    "subject": subject.model_dump(),
                    "object": obj.model_dump(),
                    "relation": rule.relation,
                    "chunk_key": c["key"],
                    "conflict_key": rule.conflict_key,
                    "decision": rule.decision,
                }
            )
            covered.add(c["key"])
    for c in chunks:
        if c["key"] not in covered:
            pending.append(
                {
                    "id": stable_id(path, c["key"]),
                    "source_path": path,
                    "heading": c["heading"],
                    "quote": c["text"],
                    "line_start": c["line_start"],
                    "line_end": c["line_end"],
                    "campus": c["campus"],
                    "reason": "requires_human_review",
                }
            )
    return facts, pending
