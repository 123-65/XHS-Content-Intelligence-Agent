from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.evidence import EvidenceRef
from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.artifact_contracts import AppendDraftVersionInput, CreateDraftVersionInput
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.definitions import ToolError, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import build_tool_handler
from app.agent.tools.query_contracts import (
    ContentOpportunityArtifactView,
    DraftArtifactView,
    EvidenceBundle,
    QueryArtifactInput,
    RetrieveResearchEvidenceInput,
)
from app.agent.tools.semantic_contracts import ReviseDraftInput, SemanticDraftResult, SemanticRevisedDraftResult
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.evidence_partition import partition_opportunity_evidence
from app.agent.workflows.registry import get_workflow
from app.agent.workflows.research import ResearchStepStatus
from app.schemas.content_strategy import EvidenceRef as StrategyEvidenceRef


STEP_IDS = (
    "draft_resolution",
    "opportunity_resolution",
    "evidence_retrieval",
    "revision",
    "draft_version_persistence",
)


class ContentRefinementWorkflowInput(BaseModel):
    """用户反馈驱动的 Draft Revision 业务输入。"""

    model_config = ConfigDict(extra="forbid")
    account_ref: int = Field(gt=0)
    draft_ref: int | None = Field(default=None, gt=0)
    user_feedback: str | None = None
    base_draft_version_ref: int | None = Field(default=None, gt=0)
    constraints: list[str] = Field(default_factory=list)


class ContentRefinementWorkflowState(BaseModel):
    """可序列化的 CONTENT_REFINEMENT_V1 恢复状态。"""

    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus = WorkflowStatus.PENDING
    account_ref: int
    draft_ref: int | None = None
    base_draft_version_ref: int | None = None
    latest_draft_version_ref: int | None = None
    latest_version: int | None = None
    draft_artifact: DraftArtifactView | None = None
    opportunity: ContentOpportunityArtifactView | None = None
    grounding_refs: list[StrategyEvidenceRef] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    evidence_bundle: EvidenceBundle | None = None
    user_feedback: str | None = None
    constraints: list[str] = Field(default_factory=list)
    revision_result: SemanticRevisedDraftResult | None = None
    new_draft_version_ref: int | None = None
    version: int | None = None
    parent_draft_ref: int | None = None
    created_from: str | None = None
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    step_states: dict[str, ResearchStepStatus] = Field(
        default_factory=lambda: {step: ResearchStepStatus.NOT_STARTED for step in STEP_IDS}
    )


class ContentRefinementWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus
    state: ContentRefinementWorkflowState
    draft_ref: int | None = None
    draft_version_ref: int | None = None
    parent_draft_ref: int | None = None
    version: int | None = None
    created_from: str | None = None
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    error: ToolError | None = None


class ContentRefinementWorkflow:
    """只把用户反馈追加为同一 Draft Root 的新 Version。"""

    workflow_id = WorkflowId.CONTENT_REFINEMENT_V1

    def __init__(self):
        self.allowlist = frozenset(get_workflow(self.workflow_id).allowed_tools)

    def execute(self, data: ContentRefinementWorkflowInput, context: ToolExecutionContext) -> ContentRefinementWorkflowResult:
        state = ContentRefinementWorkflowState(
            account_ref=data.account_ref,
            draft_ref=data.draft_ref,
            base_draft_version_ref=data.base_draft_version_ref,
            user_feedback=data.user_feedback,
            constraints=list(data.constraints),
        )
        return self._run(state, context)

    def resume(
        self,
        state: ContentRefinementWorkflowState,
        data: ContentRefinementWorkflowInput,
        context: ToolExecutionContext,
    ) -> ContentRefinementWorkflowResult:
        if data.account_ref != state.account_ref:
            return self._failed(state, self._error("VALIDATION_ERROR", "Resume account_ref 不一致。"))
        if state.draft_ref is not None and data.draft_ref not in (None, state.draft_ref):
            return self._failed(state, self._error("VALIDATION_ERROR", "同一 Workflow Run 不允许更换 Draft Root。"))
        if state.base_draft_version_ref is not None and data.base_draft_version_ref not in (None, state.base_draft_version_ref):
            return self._failed(state, self._error("DRAFT_VERSION_CONFLICT", "不允许更换 Revision 基准 Version。"))
        if state.new_draft_version_ref is not None:
            state.status = WorkflowStatus.SUCCESS
            return self._result(state)
        if state.draft_ref is None:
            state.draft_ref = data.draft_ref
        if state.base_draft_version_ref is None:
            state.base_draft_version_ref = data.base_draft_version_ref
        if not (state.user_feedback or "").strip():
            state.user_feedback = data.user_feedback
        state.constraints = list(dict.fromkeys([*state.constraints, *data.constraints]))
        state.pending_interaction = None
        return self._run(state, context)

    def _run(self, state: ContentRefinementWorkflowState, context: ToolExecutionContext) -> ContentRefinementWorkflowResult:
        state.status = WorkflowStatus.RUNNING
        if state.draft_ref is None:
            return self._waiting(state, "draft")

        previous_latest = state.latest_draft_version_ref
        result = self._call(
            ToolName.QUERY_ARTIFACT,
            QueryArtifactInput(
                account_ref=state.account_ref,
                artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=state.draft_ref),
                expected_type=ArtifactType.DRAFT,
            ),
            context,
            retry=True,
        )
        if not result.success:
            return self._tool_failed(state, "draft_resolution", result.error)
        if result.data.artifact_type != ArtifactType.DRAFT:
            return self._failed(state, self._error("VALIDATION_ERROR", "Artifact type 不是 DRAFT。"), "draft_resolution")
        current = DraftArtifactView.model_validate(result.data.content)
        if current.account_ref != state.account_ref:
            return self._failed(state, self._error("PERMISSION_ERROR", "Draft 不属于当前账号。", "PERMISSION"), "draft_resolution")
        if current.latest_draft_version_ref is None or current.latest_content is None or current.latest_version is None:
            return self._failed(
                state,
                self._error("DRAFT_VERSION_LINEAGE_MISSING", "Draft 缺少正式 Version lineage。"),
                "draft_resolution",
            )
        if previous_latest is not None and previous_latest != current.latest_draft_version_ref:
            return self._failed(state, self._conflict(), "draft_resolution")
        if state.base_draft_version_ref is not None and state.base_draft_version_ref != current.latest_draft_version_ref:
            return self._failed(state, self._conflict(), "draft_resolution")
        if current.strategy_artifact_ref is None or current.opportunity_ref is None or not current.content_goal:
            return self._failed(state, self._error("VALIDATION_ERROR", "Draft Root Identity 不完整。"), "draft_resolution")
        state.draft_artifact = current
        state.latest_draft_version_ref = current.latest_draft_version_ref
        state.latest_version = current.latest_version
        state.step_states["draft_resolution"] = ResearchStepStatus.SUCCESS

        if not (state.user_feedback or "").strip():
            return self._waiting(state, "feedback")

        if state.opportunity is None:
            result = self._call(
                ToolName.QUERY_ARTIFACT,
                QueryArtifactInput(
                    account_ref=state.account_ref,
                    artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=current.opportunity_ref),
                    expected_type=ArtifactType.CONTENT_OPPORTUNITY,
                ),
                context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "opportunity_resolution", result.error)
            opportunity = ContentOpportunityArtifactView.model_validate(result.data.content)
            if opportunity.account_ref != state.account_ref:
                return self._failed(state, self._error("PERMISSION_ERROR", "Opportunity 不属于当前账号。", "PERMISSION"), "opportunity_resolution")
            if opportunity.strategy_artifact_ref != current.strategy_artifact_ref:
                return self._failed(state, self._error("VALIDATION_ERROR", "Opportunity 与 Draft Strategy lineage 不一致。"), "opportunity_resolution")
            if opportunity.opportunity.content_goal != current.content_goal:
                return self._failed(state, self._error("VALIDATION_ERROR", "Opportunity 与 Draft content_goal 不一致。"), "opportunity_resolution")
            state.opportunity = opportunity
            state.step_states["opportunity_resolution"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["opportunity_resolution"] = ResearchStepStatus.SKIPPED

        if state.evidence_bundle is None:
            try:
                state.grounding_refs, state.evidence_refs = partition_opportunity_evidence(state.opportunity)
            except ValueError as exc:
                return self._failed(state, self._error("VALIDATION_ERROR", str(exc)), "evidence_retrieval")
            retrieval_context = ToolExecutionContext(
                db=context.db,
                evidence_access_scope=EvidenceAccessScope(authorized_refs=frozenset(state.evidence_refs)),
                collection_access_scope=context.collection_access_scope,
                runtime_identity=context.runtime_identity,
            )
            result = self._call(
                ToolName.RETRIEVE_RESEARCH_EVIDENCE,
                RetrieveResearchEvidenceInput(
                    account_ref=state.account_ref,
                    evidence_refs=state.evidence_refs,
                    purpose=current.content_goal,
                ),
                retrieval_context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "evidence_retrieval", result.error)
            if not result.data.items:
                return self._failed(state, self._error("VALIDATION_ERROR", "Opportunity Evidence 无法读取。"), "evidence_retrieval")
            state.evidence_bundle = result.data
            state.step_states["evidence_retrieval"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["evidence_retrieval"] = ResearchStepStatus.SKIPPED

        if state.revision_result is None:
            source = SemanticDraftResult(
                **current.latest_content.model_dump(),
                strategy_ref=f"CONTENT_STRATEGY:{current.strategy_artifact_ref}",
                opportunity_ref=current.opportunity_ref,
                content_goal=current.content_goal,
            )
            result = self._call(
                ToolName.REVISE_DRAFT,
                ReviseDraftInput(
                    source_draft=source,
                    revision_source="USER_FEEDBACK",
                    user_instruction=state.user_feedback.strip(),
                    preserved_constraints=list(dict.fromkeys([*state.constraints, *state.opportunity.opportunity.constraints])),
                    evidence_bundle=state.evidence_bundle,
                    opportunity=state.opportunity.opportunity,
                    grounding_refs=state.grounding_refs,
                    context_refs=[
                        ArtifactRef(type=ArtifactType.DRAFT, id=state.draft_ref),
                        ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=current.opportunity_ref),
                    ],
                ),
                context,
                retry=False,
            )
            if not result.success:
                return self._tool_failed(state, "revision", result.error)
            if (
                result.data.strategy_ref != source.strategy_ref
                or result.data.opportunity_ref != source.opportunity_ref
                or result.data.content_goal != source.content_goal
            ):
                return self._failed(state, self._error("VALIDATION_ERROR", "Revision 改变了 Draft Root Identity。"), "revision")
            state.revision_result = result.data
            state.step_states["revision"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["revision"] = ResearchStepStatus.SKIPPED

        result = self._call(
            ToolName.CREATE_DRAFT_VERSION,
            CreateDraftVersionInput(root=AppendDraftVersionInput(
                action="APPEND",
                draft_ref=state.draft_ref,
                parent_draft_ref=state.latest_draft_version_ref,
                created_from="USER_REVISION",
                content=state.revision_result,
                applied_changes=state.revision_result.applied_changes,
                context={
                    "grounding_refs": [ref.model_dump(mode="json") for ref in state.grounding_refs],
                    "evidence_refs": [ref.model_dump(mode="json") for ref in state.evidence_refs],
                    "research_artifact_ref": state.opportunity.research_artifact_ref,
                    "source_opportunity_ref": state.opportunity.source_opportunity_ref,
                },
            )),
            context,
            retry=False,
        )
        if not result.success:
            return self._tool_failed(state, "draft_version_persistence", result.error)
        if (
            result.data.draft_ref != state.draft_ref
            or result.data.parent_draft_ref != state.latest_draft_version_ref
            or result.data.version != state.latest_version + 1
            or result.data.created_from != "USER_REVISION"
            or result.data.draft_version_ref == state.latest_draft_version_ref
        ):
            return self._failed(state, self._error("VALIDATION_ERROR", "Revision Version persistence invariant 失败。"), "draft_version_persistence")
        state.new_draft_version_ref = result.data.draft_version_ref
        state.parent_draft_ref = result.data.parent_draft_ref
        state.version = result.data.version
        state.created_from = result.data.created_from
        state.step_states["draft_version_persistence"] = ResearchStepStatus.SUCCESS
        state.status = WorkflowStatus.SUCCESS
        return self._result(state)

    def _call(self, name, payload, context, retry):
        if name not in self.allowlist:
            raise ValueError(f"CONTENT_REFINEMENT_V1 Tool 越权: {name}")
        handler = build_tool_handler(name, context)
        result = handler.execute(payload)
        if retry and not result.success and result.error and result.error.retryable:
            result = handler.execute(payload)
        return result

    def _waiting(self, state, missing):
        state.status = WorkflowStatus.WAITING_USER
        state.pending_interaction = PendingInteraction(
            type=PendingInteractionType.CLARIFICATION,
            reason="需要提供要修改的 Draft。" if missing == "draft" else "请明确说明希望修改的内容。",
            required_fields=["draft_ref"] if missing == "draft" else ["user_feedback"],
            resume_token="CONTENT_REFINEMENT_V1_RESUME",
        )
        return self._result(state)

    def _tool_failed(self, state, step, error):
        return self._failed(state, error, step)

    def _failed(self, state, error, step=None):
        state.status = WorkflowStatus.FAILED
        if step:
            state.step_states[step] = ResearchStepStatus.FAILED
        return ContentRefinementWorkflowResult(
            status=state.status,
            state=state,
            draft_ref=state.draft_ref,
            draft_version_ref=state.new_draft_version_ref,
            parent_draft_ref=state.parent_draft_ref,
            version=state.version,
            created_from=state.created_from,
            warnings=state.warnings,
            error=error,
        )

    def _result(self, state):
        return ContentRefinementWorkflowResult(
            status=state.status,
            state=state,
            draft_ref=state.draft_ref,
            draft_version_ref=state.new_draft_version_ref,
            parent_draft_ref=state.parent_draft_ref,
            version=state.version,
            created_from=state.created_from,
            warnings=state.warnings,
            pending_interaction=state.pending_interaction,
        )

    def _conflict(self):
        return self._error("DRAFT_VERSION_CONFLICT", "Draft latest Version 已变化，请基于最新版本重新修改。")

    def _error(self, code, message, category="VALIDATION"):
        return ToolError(code=code, category=category, retryable=False, safe_message=message)
