from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.semantic import SemanticReferenceType, TaskSemanticFrame


class ResolvedObjectType(StrEnum):
    RESEARCH = "RESEARCH"
    CONTENT_STRATEGY = "CONTENT_STRATEGY"
    CONTENT_OPPORTUNITY = "CONTENT_OPPORTUNITY"
    DRAFT = "DRAFT"
    PUBLISHED_NOTE = "PUBLISHED_NOTE"
    RUN = "RUN"
    ACCOUNT = "ACCOUNT"


class ResolutionSource(StrEnum):
    CURRENT_TURN_MATERIAL = "CURRENT_TURN_MATERIAL"
    EXPLICIT_SELECTION = "EXPLICIT_SELECTION"
    WORKSPACE_SELECTION = "WORKSPACE_SELECTION"
    PENDING_CONTEXT = "PENDING_CONTEXT"
    ACTIVE_CONTEXT = "ACTIVE_CONTEXT"
    RECENT_CONVERSATION = "RECENT_CONVERSATION"
    HISTORY = "HISTORY"
    ORDINAL_SELECTION = "ORDINAL_SELECTION"
    TEMPORAL_SELECTION = "TEMPORAL_SELECTION"


class ObjectRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: ResolvedObjectType
    id: int | str


class TrustedContextRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: ObjectRef
    account_ref: int = Field(gt=0)


class OpportunityCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_ref: TrustedContextRef
    opportunity_refs: list[TrustedContextRef]


class StructuredContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    references: list[TrustedContextRef] = Field(default_factory=list)
    opportunity_collections: list[OpportunityCollection] = Field(default_factory=list)
    review_refs: list[int] = Field(default_factory=list)


class ContextResolverInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_ref: int = Field(gt=0)
    semantic_frame: TaskSemanticFrame
    current_turn_materials: list["CurrentTurnMaterialCandidate"] = Field(default_factory=list)
    explicit_references: list[TrustedContextRef] = Field(default_factory=list)
    workspace_selection: StructuredContext = Field(default_factory=StructuredContext)
    pending_context: StructuredContext | None = None
    active_context: StructuredContext = Field(default_factory=StructuredContext)
    conversation_context: StructuredContext = Field(default_factory=StructuredContext)
    history_context: StructuredContext = Field(default_factory=StructuredContext)


class IdentityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: ObjectRef
    account_ref: int
    published_at: datetime | None = None
    external_identity: str | None = None


class CurrentTurnMaterialType(StrEnum):
    PROFILE = "PROFILE"
    NOTE = "NOTE"


class CurrentTurnMaterialCandidate(BaseModel):
    """Authorized external material; never represents a persisted canonical ObjectRef."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    type: CurrentTurnMaterialType
    account_ref: int = Field(gt=0)
    source_url: str
    external_identity: str


class ContextIdentityReader(Protocol):
    def get_identity(self, ref: ObjectRef) -> IdentityRecord | None: ...
    def list_published_between(self, account_ref: int, start: datetime, end: datetime) -> list[IdentityRecord]: ...
    def latest_published(self, account_ref: int) -> IdentityRecord | None: ...


class ResolutionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_text: str
    source: ResolutionSource
    priority: int = Field(ge=1, le=8)
    candidate_count: int = Field(ge=0)
    context_strategy_ref: ObjectRef | None = None


class ResolvedReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_type: SemanticReferenceType
    raw_text: str
    resolved_ref: ObjectRef
    resolved_object_type: ResolvedObjectType
    resolution_source: ResolutionSource
    confidence: float = Field(ge=0, le=1)
    deterministic: bool = True


class UnresolvedReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_type: SemanticReferenceType
    raw_text: str
    reason: str


class AmbiguousReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_type: SemanticReferenceType
    raw_text: str
    candidate_refs: list[ObjectRef]
    candidate_materials: list[str] = Field(default_factory=list)
    reason: str


class MaterialSatisfiedReference(BaseModel):
    """A language reference located by current-turn material without claiming canonical identity."""

    model_config = ConfigDict(extra="forbid")
    reference_type: SemanticReferenceType
    raw_text: str
    material_type: CurrentTurnMaterialType
    external_identity: str
    resolution_source: ResolutionSource = ResolutionSource.CURRENT_TURN_MATERIAL
    deterministic: bool = True


class ResolvedContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_ref: int
    resolved_references: list[ResolvedReference] = Field(default_factory=list)
    material_satisfied_references: list[MaterialSatisfiedReference] = Field(default_factory=list)
    unresolved_references: list[UnresolvedReference] = Field(default_factory=list)
    ambiguous_references: list[AmbiguousReference] = Field(default_factory=list)
    context_facts: dict[str, ObjectRef] = Field(default_factory=dict)
    resolution_trace: list[ResolutionTrace] = Field(default_factory=list)
    blocking_missing_info: list[str] = Field(default_factory=list)
