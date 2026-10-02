from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.evidence import EvidenceRef
from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.artifact_contracts import CreateDraftV1Input, CreateDraftVersionInput
from app.agent.tools.definitions import ToolError, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.implementation_registry import build_tool_handler
from app.agent.tools.query_contracts import (
    ContentOpportunityArtifactView,
    ContentStrategyArtifactView,
    EvidenceBundle,
    GrowthContextSection,
    QueryArtifactInput,
    QueryGrowthContextInput,
    RetrieveResearchEvidenceInput,
)
from app.agent.tools.semantic_contracts import GenerateDraftInput, ReviewDraftInput, SemanticDraftResult
from app.schemas.content_strategy import EvidenceRef as StrategyEvidenceRef
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.evidence_partition import partition_opportunity_evidence
from app.agent.workflows.registry import get_workflow
from app.agent.workflows.research import ResearchStepStatus
from app.schemas.draft import DraftReviewLLMResult


STEP_IDS = (
    "growth_context",
    "strategy_artifact",
    "opportunity_resolution",
    "opportunity_artifact",
    "evidence_retrieval",
    "draft_generation",
    "draft_persistence",
    "draft_review",
)


class ContentCreationWorkflowInput(BaseModel):
    """CONTENT_CREATION_V1 的纯业务输入，身份字段由持久化 Artifact 决定。"""

    model_config = ConfigDict(extra="forbid")
    account_ref: int = Field(gt=0)
    strategy_artifact_ref: ArtifactRef | None = None
    opportunity_ref: int | None = Field(default=None, gt=0)
    constraints: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)


class ContentCreationWorkflowState(BaseModel):
    """可序列化的 CONTENT_CREATION_V1 恢复状态。"""

    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus = WorkflowStatus.PENDING
    account_ref: int
    constraints: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)
    growth_context: dict[str, Any] | None = None
    strategy_artifact_ref: ArtifactRef | None = None
    strategy_artifact: ContentStrategyArtifactView | None = None
    opportunity_ref: int | None = None
    opportunity: ContentOpportunityArtifactView | None = None
    grounding_refs: list[StrategyEvidenceRef] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    evidence_bundle: EvidenceBundle | None = None
    draft_generation_result: SemanticDraftResult | None = None
    draft_ref: int | None = None
    draft_version_ref: int | None = None
    version: int | None = None
    review_result: DraftReviewLLMResult | None = None
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    step_states: dict[str, ResearchStepStatus] = Field(
        default_factory=lambda: {step: ResearchStepStatus.NOT_STARTED for step in STEP_IDS}
    )


class ContentCreationWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus
    state: ContentCreationWorkflowState
    draft_ref: int | None = None
    draft_version_ref: int | None = None
    version: int | None = None
    strategy_artifact_ref: ArtifactRef | None = None
    opportunity_ref: int | None = None
    review_result: DraftReviewLLMResult | None = None
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    error: ToolError | None = None


class ContentCreationWorkflow:
    """确定性编排 Strategy、Evidence、Draft V1 与只读 Review。"""

    workflow_id = WorkflowId.CONTENT_CREATION_V1

    def __init__(self):
        self.allowlist = frozenset(get_workflow(self.workflow_id).allowed_tools)

    def execute(self, data: ContentCreationWorkflowInput, context: ToolExecutionContext) -> ContentCreationWorkflowResult:
        state = ContentCreationWorkflowState(
            account_ref=data.account_ref,
            constraints=list(data.constraints),
            style_constraints=list(data.style_constraints),
            strategy_artifact_ref=data.strategy_artifact_ref,
            opportunity_ref=data.opportunity_ref,
        )
        return self._run(state, context)

    def resume(
        self,
        state: ContentCreationWorkflowState,
        data: ContentCreationWorkflowInput,
        context: ToolExecutionContext,
    ) -> ContentCreationWorkflowResult:
        if data.account_ref != state.account_ref:
            return self._failed(state, self._validation_error("Resume account_ref 不一致。"))
        if state.strategy_artifact_ref is not None and data.strategy_artifact_ref not in (None, state.strategy_artifact_ref):
            return self._failed(state, self._validation_error("同一 Workflow Run 不允许更换 Strategy Artifact。"))
        if state.opportunity_ref is not None and data.opportunity_ref not in (None, state.opportunity_ref):
            return self._failed(state, self._validation_error("同一 Workflow Run 不允许更换 Opportunity。"))
        if state.status == WorkflowStatus.SUCCESS:
            return self._result(state)
        if state.strategy_artifact_ref is None:
            state.strategy_artifact_ref = data.strategy_artifact_ref
        if state.opportunity_ref is None:
            state.opportunity_ref = data.opportunity_ref
        state.constraints = list(dict.fromkeys([*state.constraints, *data.constraints]))
        state.style_constraints = list(dict.fromkeys([*state.style_constraints, *data.style_constraints]))
        state.pending_interaction = None
        return self._run(state, context)

    def _run(self, state: ContentCreationWorkflowState, context: ToolExecutionContext) -> ContentCreationWorkflowResult:
        state.status = WorkflowStatus.RUNNING
        if state.growth_context is None:
            result = self._call(
                ToolName.QUERY_GROWTH_CONTEXT,
                QueryGrowthContextInput(account_ref=state.account_ref, requested_sections=list(GrowthContextSection)),
                context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "growth_context", result.error)
            state.growth_context = result.data.model_dump(mode="json")
            state.step_states["growth_context"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["growth_context"] = ResearchStepStatus.SKIPPED

        if state.strategy_artifact_ref is None:
            return self._waiting(state, "strategy")
        if state.strategy_artifact_ref.type != ArtifactType.CONTENT_STRATEGY:
            return self._failed(state, self._validation_error("显式 Artifact 引用必须为 CONTENT_STRATEGY。"), "strategy_artifact")
        if state.strategy_artifact is None:
            result = self._call(
                ToolName.QUERY_ARTIFACT,
                QueryArtifactInput(
                    account_ref=state.account_ref,
                    artifact_ref=state.strategy_artifact_ref,
                    expected_type=ArtifactType.CONTENT_STRATEGY,
                ),
                context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "strategy_artifact", result.error)
            if result.data.artifact_type != ArtifactType.CONTENT_STRATEGY:
                return self._failed(state, self._validation_error("Artifact type 不是 CONTENT_STRATEGY。"), "strategy_artifact")
            state.strategy_artifact = ContentStrategyArtifactView.model_validate(result.data.content)
            if state.strategy_artifact.account_ref != state.account_ref:
                return self._failed(state, self._validation_error("Content Strategy 不属于当前账号。"), "strategy_artifact")
            state.step_states["strategy_artifact"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["strategy_artifact"] = ResearchStepStatus.SKIPPED

        if state.opportunity_ref is None:
            choices = state.strategy_artifact.generated_opportunity_refs
            if not choices:
                return self._failed(state, self._validation_error("Content Strategy 没有可执行 Opportunity。"), "opportunity_resolution")
            if len(choices) > 1:
                return self._waiting(state, "opportunity")
            state.opportunity_ref = choices[0]
        state.step_states["opportunity_resolution"] = ResearchStepStatus.SUCCESS

        if state.opportunity is None:
            result = self._call(
                ToolName.QUERY_ARTIFACT,
                QueryArtifactInput(
                    account_ref=state.account_ref,
                    artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=state.opportunity_ref),
                    expected_type=ArtifactType.CONTENT_OPPORTUNITY,
                ),
                context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "opportunity_artifact", result.error)
            if result.data.artifact_type != ArtifactType.CONTENT_OPPORTUNITY:
                return self._failed(state, self._validation_error("Artifact type 不是 CONTENT_OPPORTUNITY。"), "opportunity_artifact")
            state.opportunity = ContentOpportunityArtifactView.model_validate(result.data.content)
            if state.opportunity.account_ref != state.account_ref:
                return self._failed(state, self._validation_error("Opportunity 不属于当前账号。"), "opportunity_artifact")
            if state.opportunity.strategy_artifact_ref != state.strategy_artifact_ref.id:
                return self._failed(state, self._validation_error("Opportunity 不属于当前 Content Strategy。"), "opportunity_artifact")
            state.step_states["opportunity_artifact"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["opportunity_artifact"] = ResearchStepStatus.SKIPPED

        if state.evidence_bundle is None:
            try:
                state.grounding_refs, state.evidence_refs = partition_opportunity_evidence(state.opportunity)
            except ValueError as exc:
                return self._failed(state, self._validation_error(str(exc)), "evidence_retrieval")
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
                    purpose=state.opportunity.opportunity.content_goal,
                ),
                retrieval_context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "evidence_retrieval", result.error)
            if not result.data.items:
                return self._failed(state, self._validation_error("Opportunity Evidence 无法读取。"), "evidence_retrieval")
            state.evidence_bundle = result.data
            state.step_states["evidence_retrieval"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["evidence_retrieval"] = ResearchStepStatus.SKIPPED

        if state.draft_generation_result is None:
            strategy = state.strategy_artifact.model_dump(mode="json")
            strategy["strategy_ref"] = self._strategy_ref(state)
            result = self._call(
                ToolName.GENERATE_DRAFT,
                GenerateDraftInput(
                    account_context=state.growth_context,
                    strategy=strategy,
                    strategy_ref=self._strategy_ref(state),
                    opportunity=state.opportunity.opportunity,
                    evidence_bundle=state.evidence_bundle,
                    user_constraints=list(dict.fromkeys([*state.constraints, *state.opportunity.opportunity.constraints])),
                    style_constraints=state.style_constraints,
                ),
                context,
                retry=False,
            )
            if not result.success:
                return self._tool_failed(state, "draft_generation", result.error)
            state.draft_generation_result = result.data
            state.step_states["draft_generation"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["draft_generation"] = ResearchStepStatus.SKIPPED

        if state.draft_version_ref is None:
            request = CreateDraftVersionInput(root=CreateDraftV1Input(
                action="CREATE_V1",
                account_ref=state.account_ref,
                strategy_artifact_ref=state.strategy_artifact_ref.id,
                opportunity_ref=state.opportunity_ref,
                content_goal=state.opportunity.opportunity.content_goal,
                content=state.draft_generation_result,
                context={
                    "grounding_refs": [ref.model_dump(mode="json") for ref in state.grounding_refs],
                    "evidence_refs": [ref.model_dump(mode="json") for ref in state.evidence_refs],
                    "research_artifact_ref": state.opportunity.research_artifact_ref,
                    "source_opportunity_ref": state.opportunity.source_opportunity_ref,
                },
            ))
            result = self._call(ToolName.CREATE_DRAFT_VERSION, request, context, retry=False)
            if not result.success:
                return self._tool_failed(state, "draft_persistence", result.error)
            if result.data.version != 1 or result.data.parent_draft_ref is not None or result.data.created_from != "GENERATED":
                return self._failed(state, self._validation_error("Draft V1 持久化结果语义不合法。"), "draft_persistence")
            state.draft_ref = result.data.draft_ref
            state.draft_version_ref = result.data.draft_version_ref
            state.version = result.data.version
            state.step_states["draft_persistence"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["draft_persistence"] = ResearchStepStatus.SKIPPED

        if state.review_result is None:
            result = self._call(
                ToolName.REVIEW_DRAFT,
                ReviewDraftInput(
                    draft=state.draft_generation_result,
                    strategy=state.strategy_artifact.model_dump(mode="json"),
                    opportunity=state.opportunity.opportunity,
                    evidence_bundle=state.evidence_bundle,
                    grounding_refs=state.grounding_refs,
                    account_context=state.growth_context,
                    review_constraints=list(dict.fromkeys([*state.constraints, *state.style_constraints])),
                ),
                context,
                retry=False,
            )
            if not result.success:
                state.status = WorkflowStatus.PARTIAL_SUCCESS
                state.step_states["draft_review"] = ResearchStepStatus.FAILED
                state.warnings = list(dict.fromkeys([*state.warnings, "DRAFT_REVIEW_FAILED"]))
                return self._result(state)
            state.review_result = result.data
            state.step_states["draft_review"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["draft_review"] = ResearchStepStatus.SKIPPED
        state.status = WorkflowStatus.SUCCESS
        return self._result(state)

    def _call(self, name, payload, context, retry):
        if name not in self.allowlist:
            raise ValueError(f"CONTENT_CREATION_V1 Tool 越权: {name}")
        handler = build_tool_handler(name, context)
        result = handler.execute(payload)
        if retry and not result.success and result.error and result.error.retryable:
            result = handler.execute(payload)
        return result

    def _waiting(self, state, missing):
        state.status = WorkflowStatus.WAITING_USER
        if missing == "strategy":
            state.step_states["strategy_artifact"] = ResearchStepStatus.WAITING_USER
            reason = "需要提供或选择一个 Content Strategy Artifact。"
            fields = ["strategy_artifact_ref"]
        else:
            state.step_states["opportunity_resolution"] = ResearchStepStatus.WAITING_USER
            reason = "当前 Strategy 包含多个 Opportunity，请选择一个具体 Opportunity。"
            fields = ["opportunity_ref"]
        state.pending_interaction = PendingInteraction(
            type=PendingInteractionType.CLARIFICATION,
            reason=reason,
            required_fields=fields,
            resume_token="CONTENT_CREATION_V1_RESUME",
        )
        return self._result(state)

    def _tool_failed(self, state, step, error):
        return self._failed(state, error, step)

    def _failed(self, state, error, step=None):
        state.status = WorkflowStatus.FAILED
        if step:
            state.step_states[step] = ResearchStepStatus.FAILED
        return ContentCreationWorkflowResult(
            status=state.status,
            state=state,
            draft_ref=state.draft_ref,
            draft_version_ref=state.draft_version_ref,
            version=state.version,
            strategy_artifact_ref=state.strategy_artifact_ref,
            opportunity_ref=state.opportunity_ref,
            warnings=state.warnings,
            error=error,
        )

    def _result(self, state):
        return ContentCreationWorkflowResult(
            status=state.status,
            state=state,
            draft_ref=state.draft_ref,
            draft_version_ref=state.draft_version_ref,
            version=state.version,
            strategy_artifact_ref=state.strategy_artifact_ref,
            opportunity_ref=state.opportunity_ref,
            review_result=state.review_result,
            warnings=state.warnings,
            pending_interaction=state.pending_interaction,
        )

    def _strategy_ref(self, state):
        return f"CONTENT_STRATEGY:{state.strategy_artifact_ref.id}"

    def _validation_error(self, message):
        return ToolError(code="VALIDATION_ERROR", category="VALIDATION", retryable=False, safe_message=message)
