"""Canonical server-verified facts used for conversation-v2 tool arbitration."""

from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.agent.control.current_turn_materials import (
    CurrentMaterialSource,
    CurrentMaterialType,
    NormalizedCurrentMaterial,
)
from app.agent.conversation_v2.workspace import RecentTrustedContext, TrustedWorkspaceSnapshot
from app.agent.workflows.definitions import WorkflowId


class DecisionObjectType(StrEnum):
    RESEARCH_ARTIFACT = "RESEARCH_ARTIFACT"
    CONTENT_STRATEGY = "CONTENT_STRATEGY"
    OPPORTUNITY = "OPPORTUNITY"
    DRAFT = "DRAFT"
    PUBLISHED_NOTE = "PUBLISHED_NOTE"


class DecisionObjectSource(StrEnum):
    WORKSPACE = "WORKSPACE"
    RECENT_CONTEXT = "RECENT_CONTEXT"


class MaterialFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    material_type: CurrentMaterialType
    count: int = Field(gt=0)
    source: CurrentMaterialSource


class ObjectFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    object_type: DecisionObjectType
    source: DecisionObjectSource
    exists: bool
    owned: bool
    lineage_valid: bool | None = None


class PendingFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_type: WorkflowId
    required_fields: tuple[str, ...] = ()
    resumable: bool
    requirements_satisfied: bool


class ToolCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    workflow_type: WorkflowId
    accepts_current_materials: frozenset[CurrentMaterialType] = frozenset()
    eligible_context: frozenset[DecisionObjectType] = frozenset()
    bootstrap_without_material: bool = False


TOOL_CAPABILITIES: dict[str, ToolCapability] = {
    "run_research": ToolCapability(
        tool_name="run_research",
        workflow_type=WorkflowId.RESEARCH_V1,
        accepts_current_materials=frozenset({
            CurrentMaterialType.EXTERNAL_XHS_PROFILE,
            CurrentMaterialType.EXTERNAL_XHS_NOTE,
        }),
        bootstrap_without_material=True,
    ),
    "run_content_strategy": ToolCapability(
        tool_name="run_content_strategy",
        workflow_type=WorkflowId.CONTENT_STRATEGY_V1,
        eligible_context=frozenset({DecisionObjectType.RESEARCH_ARTIFACT}),
    ),
    "run_content_creation": ToolCapability(
        tool_name="run_content_creation",
        workflow_type=WorkflowId.CONTENT_CREATION_V1,
        eligible_context=frozenset({DecisionObjectType.OPPORTUNITY}),
    ),
    "run_content_refinement": ToolCapability(
        tool_name="run_content_refinement",
        workflow_type=WorkflowId.CONTENT_REFINEMENT_V1,
        eligible_context=frozenset({DecisionObjectType.DRAFT}),
    ),
    "run_post_publish_review": ToolCapability(
        tool_name="run_post_publish_review",
        workflow_type=WorkflowId.POST_PUBLISH_REVIEW_V1,
        eligible_context=frozenset({DecisionObjectType.PUBLISHED_NOTE}),
    ),
}


class CanonicalTurnContext(BaseModel):
    """One immutable decision projection; never contains raw URLs or artifact bodies."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    current_materials: tuple[MaterialFact, ...] = ()
    workspace_objects: tuple[ObjectFact, ...] = ()
    recent_object_types: tuple[ObjectFact, ...] = ()
    pending: PendingFact | None = None
    candidate_tools: tuple[str, ...] = ()

    @property
    def current_material_types(self) -> frozenset[CurrentMaterialType]:
        return frozenset(item.material_type for item in self.current_materials)

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.candidate_tools

    def prompt_text(self) -> str:
        materials = [
            {
                "material_type": item.material_type.value,
                "count": item.count,
                "source": item.source.value,
            }
            for item in self.current_materials
        ]
        workspace = [item.object_type.value for item in self.workspace_objects if item.exists and item.owned]
        recent = [item.object_type.value for item in self.recent_object_types if item.exists and item.owned]
        pending = None
        if self.pending is not None:
            pending = {
                "workflow_type": self.pending.workflow_type.value,
                "required_fields": list(self.pending.required_fields),
                "resumable": self.pending.resumable,
                "requirements_satisfied": self.pending.requirements_satisfied,
            }
        return (
            "Current turn facts (server verified; object presence is eligibility, not intent):\n"
            f"- Materials: {materials or 'none'}\n"
            f"- Workspace object types: {workspace or 'none'}\n"
            f"- Recent trusted object types: {recent or 'none'}\n"
            f"- Pending: {pending or 'none'}\n"
            f"- Eligible workflow tools: {list(self.candidate_tools) or 'none'}"
        )


class ToolEligibilityPolicy:
    """Filter by verified input compatibility; never infer user intent from text."""

    @classmethod
    def candidates(cls, context: CanonicalTurnContext) -> tuple[str, ...]:
        material_types = context.current_material_types
        pending = context.pending
        if pending and pending.resumable and pending.requirements_satisfied:
            for capability in TOOL_CAPABILITIES.values():
                if capability.workflow_type == pending.workflow_type and material_types <= capability.accepts_current_materials:
                    return (capability.tool_name,)
            return ()

        if material_types:
            return tuple(
                capability.tool_name
                for capability in TOOL_CAPABILITIES.values()
                if material_types <= capability.accepts_current_materials
            )

        available = {
            item.object_type
            for item in (*context.workspace_objects, *context.recent_object_types)
            if item.exists and item.owned
        }
        candidates: list[str] = []
        for capability in TOOL_CAPABILITIES.values():
            if capability.bootstrap_without_material:
                candidates.append(capability.tool_name)
                continue
            if not capability.eligible_context <= available:
                continue
            if capability.tool_name == "run_content_creation" and not cls._has_valid_opportunity_lineage(context):
                continue
            candidates.append(capability.tool_name)
        return tuple(candidates)

    @staticmethod
    def _has_valid_opportunity_lineage(context: CanonicalTurnContext) -> bool:
        return any(
            item.object_type == DecisionObjectType.OPPORTUNITY
            and item.exists
            and item.owned
            and item.lineage_valid is True
            for item in (*context.workspace_objects, *context.recent_object_types)
        )


class CanonicalTurnContextBuilder:
    def build(
        self,
        *,
        current_materials: tuple[NormalizedCurrentMaterial, ...],
        workspace: TrustedWorkspaceSnapshot,
        recent: RecentTrustedContext,
        pending: PendingFact | None,
    ) -> CanonicalTurnContext:
        counts = Counter((item.material_type, item.source) for item in current_materials)
        material_facts = tuple(
            MaterialFact(material_type=material_type, source=source, count=count)
            for (material_type, source), count in counts.items()
        )
        context = CanonicalTurnContext(
            current_materials=material_facts,
            workspace_objects=self._object_facts(workspace, DecisionObjectSource.WORKSPACE),
            recent_object_types=self._object_facts(recent, DecisionObjectSource.RECENT_CONTEXT),
            pending=pending,
        )
        return context.model_copy(update={"candidate_tools": ToolEligibilityPolicy.candidates(context)})

    @staticmethod
    def _object_facts(
        snapshot: TrustedWorkspaceSnapshot | RecentTrustedContext,
        source: DecisionObjectSource,
    ) -> tuple[ObjectFact, ...]:
        values = (
            (DecisionObjectType.RESEARCH_ARTIFACT, snapshot.research_ref, None),
            (DecisionObjectType.CONTENT_STRATEGY, snapshot.strategy_ref, None),
            (
                DecisionObjectType.OPPORTUNITY,
                snapshot.opportunity_ref,
                bool(snapshot.opportunity_strategy_ref) if snapshot.opportunity_ref is not None else None,
            ),
            (DecisionObjectType.DRAFT, snapshot.draft_ref, None),
            (DecisionObjectType.PUBLISHED_NOTE, snapshot.published_note_ref, None),
        )
        return tuple(
            ObjectFact(
                object_type=object_type,
                source=source,
                exists=True,
                owned=True,
                lineage_valid=lineage_valid,
            )
            for object_type, ref, lineage_valid in values
            if ref is not None
        )


def pending_requirements_satisfied(
    workflow_type: WorkflowId,
    required_fields: tuple[str, ...],
    material_types: frozenset[CurrentMaterialType],
) -> bool:
    """Recognize only frozen, objective continuation fields supported in B2."""
    if workflow_type != WorkflowId.RESEARCH_V1:
        return not required_fields
    supported = {"research_material"}
    return set(required_fields) <= supported and (
        not required_fields
        or bool(material_types & TOOL_CAPABILITIES["run_research"].accepts_current_materials)
    )
