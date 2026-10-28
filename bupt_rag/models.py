from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Campus = Literal["shahe", "haidian", "shared", "unknown"]
SelectedCampus = Literal["shahe", "haidian"]
EntityType = Literal["Campus", "Place", "Service", "Platform", "Condition"]
Relation = Literal["LOCATED_IN", "PROVIDES", "USES_PLATFORM", "REQUIRES"]


class Document(StrictModel):
    id: str
    title: str
    source_path: str
    source_commit: str
    source_url: str


class Entity(StrictModel):
    id: str
    type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    campus: Campus
    url: str | None = None


class Edge(StrictModel):
    subject_id: str
    relation: Relation
    object_id: str
    evidence_ids: list[str]


class Evidence(StrictModel):
    id: str
    doc_id: str
    source_commit: str
    source_path: str
    heading: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str
    source_url: str


class GraphPath(StrictModel):
    id: str
    branch_id: int = 0
    nodes: list[Entity]
    edges: list[Edge]


class Answer(StrictModel):
    text: str
    entity_ids: list[str] = Field(default_factory=list)
    path_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Option(StrictModel):
    value: str
    label: str


class Clarification(StrictModel):
    field: Literal["campus", "entity_bindings"]
    mention: str
    options: list[Option]


class QARequest(StrictModel):
    question: str = Field(min_length=1, max_length=2000)
    campus: SelectedCampus | None = None
    mode: Literal["hybrid", "vector"] = "hybrid"
    entity_bindings: dict[str, str] = Field(default_factory=dict)

    @field_validator("question")
    @classmethod
    def nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class QAResponse(StrictModel):
    status: Literal["answered", "partial", "abstained", "needs_clarification"]
    reason: str | None = None
    knowledge_revision: int
    source_commit: str
    answers: list[Answer] = Field(default_factory=list)
    paths: list[GraphPath] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarifications: list[Clarification] = Field(default_factory=list)


class SyncRequest(StrictModel):
    ref: str = Field(default="main", min_length=1, max_length=200, pattern=r"^[\w./-]+$")


class SyncResponse(StrictModel):
    source_commit: str
    knowledge_revision: int
    added: int = Field(ge=0)
    updated: int = Field(ge=0)
    deleted: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    changed: bool


class KnowledgeStatus(StrictModel):
    repository: str
    source_commit: str | None
    knowledge_revision: int
    document_count: int
    last_synced_at: str | None


class DocumentList(StrictModel):
    items: list[Document]


class DocumentDetail(StrictModel):
    document: Document
    text: str


class EntityList(StrictModel):
    items: list[Entity]


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorDetail


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)
