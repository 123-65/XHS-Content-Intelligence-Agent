from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.artifact_contracts import CreateContentStrategyArtifactInput
from app.agent.tools.definitions import ToolError, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import build_tool_handler
from app.agent.tools.query_contracts import GrowthContextSection, QueryArtifactInput, QueryGrowthContextInput
from app.agent.tools.semantic_contracts import GenerateContentStrategyInput
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.registry import get_workflow
from app.agent.workflows.research import ResearchStepStatus
from app.schemas.content_strategy import ContentOpportunityResult, ContentStrategyResult, EvidenceRef, GeneratedContentStrategy


STEP_IDS = ("growth_context", "research_artifact", "strategy_generation", "strategy_artifact_creation")


class ContentStrategyWorkflowInput(BaseModel):
    """CONTENT_STRATEGY_V1 的纯业务输入。"""

    model_config = ConfigDict(extra="forbid")
    account_ref: int = Field(gt=0)
    research_artifact_ref: ArtifactRef | None = None
    strategy_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


class ContentStrategyWorkflowState(BaseModel):
    """可序列化的 CONTENT_STRATEGY_V1 恢复状态。"""

    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus = WorkflowStatus.PENDING
    account_ref: int
    strategy_goal: str
    constraints: list[str] = Field(default_factory=list)
    growth_context: dict[str, Any] | None = None
    research_artifact_ref: ArtifactRef | None = None
    research_artifact: dict[str, Any] | None = None
    strategy_result: ContentStrategyResult | None = None
    strategy_artifact_ref: ArtifactRef | None = None
    generated_opportunity_refs: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    step_states: dict[str, ResearchStepStatus] = Field(
        default_factory=lambda: {step: ResearchStepStatus.NOT_STARTED for step in STEP_IDS}
    )


class ContentStrategyWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus
    state: ContentStrategyWorkflowState
    strategy_artifact_ref: ArtifactRef | None = None
    generated_opportunity_refs: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    error: ToolError | None = None


class ContentStrategyWorkflow:
    """只编排冻结 Tool 的确定性 CONTENT_STRATEGY_V1。"""

    workflow_id = WorkflowId.CONTENT_STRATEGY_V1

    def __init__(self):
        self.allowlist = frozenset(get_workflow(self.workflow_id).allowed_tools)

    def execute(self, data: ContentStrategyWorkflowInput, context: ToolExecutionContext) -> ContentStrategyWorkflowResult:
        state = ContentStrategyWorkflowState(
            account_ref=data.account_ref,
            strategy_goal=data.strategy_goal,
            constraints=list(data.constraints),
            research_artifact_ref=data.research_artifact_ref,
        )
        return self._run(state, context)

    def resume(
        self,
        state: ContentStrategyWorkflowState,
        data: ContentStrategyWorkflowInput,
        context: ToolExecutionContext,
    ) -> ContentStrategyWorkflowResult:
        if data.account_ref != state.account_ref:
            return self._failed(state, self._validation_error("Resume account_ref 不一致。"))
        if state.research_artifact_ref is not None and data.research_artifact_ref not in (None, state.research_artifact_ref):
            return self._failed(state, self._validation_error("同一 Workflow Run 不允许更换 Research Artifact。"))
        if state.strategy_artifact_ref is not None:
            state.status = WorkflowStatus.SUCCESS
            return self._result(state)
        if state.research_artifact_ref is None:
            state.research_artifact_ref = data.research_artifact_ref
        state.pending_interaction = None
        state.constraints = list(dict.fromkeys([*state.constraints, *data.constraints]))
        return self._run(state, context)

    def _run(self, state: ContentStrategyWorkflowState, context: ToolExecutionContext) -> ContentStrategyWorkflowResult:
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

        if state.research_artifact_ref is None:
            return self._waiting(state)
        if state.research_artifact_ref.type != ArtifactType.RESEARCH:
            return self._failed(state, self._validation_error("显式 Artifact 引用必须为 RESEARCH。"), "research_artifact")

        if state.research_artifact is None:
            result = self._call(
                ToolName.QUERY_ARTIFACT,
                QueryArtifactInput(
                    account_ref=state.account_ref,
                    artifact_ref=state.research_artifact_ref,
                    expected_type=ArtifactType.RESEARCH,
                ),
                context,
                retry=True,
            )
            if not result.success:
                return self._tool_failed(state, "research_artifact", result.error)
            if result.data.artifact_type != ArtifactType.RESEARCH:
                return self._failed(state, self._validation_error("Artifact type 不是 RESEARCH。"), "research_artifact")
            content = result.data.content
            if content.get("account_id") not in (None, state.account_ref):
                return self._failed(state, self._validation_error("Research Artifact 不属于当前账号。"), "research_artifact")
            state.research_artifact = result.data.model_dump(mode="json")
            state.step_states["research_artifact"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["research_artifact"] = ResearchStepStatus.SKIPPED

        if state.strategy_result is None:
            content = dict(state.research_artifact["content"])
            content["strategy_goal"] = state.strategy_goal
            semantic = self._call(
                ToolName.GENERATE_CONTENT_STRATEGY,
                GenerateContentStrategyInput(
                    account_ref=state.account_ref,
                    growth_context=state.growth_context,
                    research_result=content,
                    historical_opportunities=list(content.get("content_opportunities", [])),
                    strategy_memory=list(state.growth_context.get("strategy_memory", [])),
                    evidence_refs=[EvidenceRef(kind="research_report", id=state.research_artifact_ref.id)],
                    constraints=state.constraints,
                ),
                context,
                retry=False,
            )
            if not semantic.success:
                return self._tool_failed(state, "strategy_generation", semantic.error)
            state.strategy_result = self._to_persistence_result(semantic.data, state, semantic.metadata)
            state.warnings = list(dict.fromkeys([*state.warnings, *semantic.warnings]))
            state.step_states["strategy_generation"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["strategy_generation"] = ResearchStepStatus.SKIPPED

        artifact = self._call(
            ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT,
            CreateContentStrategyArtifactInput(
                account_ref=state.account_ref,
                research_artifact_ref=state.research_artifact_ref.id,
                strategy_result=state.strategy_result,
            ),
            context,
            retry=False,
        )
        if not artifact.success:
            return self._tool_failed(state, "strategy_artifact_creation", artifact.error)
        state.strategy_artifact_ref = artifact.data.artifact_ref
        state.generated_opportunity_refs = list(artifact.data.generated_opportunity_refs)
        state.warnings = list(dict.fromkeys([*state.warnings, *artifact.warnings]))
        state.step_states["strategy_artifact_creation"] = ResearchStepStatus.SUCCESS
        state.status = WorkflowStatus.SUCCESS
        return self._result(state)

    def _to_persistence_result(self, generated: GeneratedContentStrategy, state, metadata) -> ContentStrategyResult:
        opportunities = [
            ContentOpportunityResult(
                source_opportunity_id=item.source_opportunity_id,
                topic=item.content_goal,
                angle=item.why_now,
                target_audience=generated.target_audience,
                content_goal=item.content_goal,
                why_now=item.why_now,
                evidence_refs=item.evidence_refs,
                suggested_hook=item.suggested_hook,
                constraints=item.constraints,
            )
            for item in generated.opportunities
        ]
        return ContentStrategyResult(
            account_id=state.account_ref,
            research_report_id=state.research_artifact_ref.id,
            strategy_goal=generated.strategy_goal,
            target_audience=generated.target_audience,
            content_directions=generated.content_directions,
            rationale=generated.rationale,
            evidence_refs=generated.evidence_refs,
            applicable_constraints=generated.applicable_constraints,
            opportunities=opportunities,
            provider=str(metadata.get("provider", "unspecified")),
            model=str(metadata.get("model", "unspecified")),
        )

    def _call(self, name, payload, context, retry):
        if name not in self.allowlist:
            raise ValueError(f"CONTENT_STRATEGY_V1 Tool 越权: {name}")
        handler = build_tool_handler(name, context)
        result = handler.execute(payload)
        if retry and not result.success and result.error and result.error.retryable:
            result = handler.execute(payload)
        return result

    def _waiting(self, state):
        state.status = WorkflowStatus.WAITING_USER
        state.step_states["research_artifact"] = ResearchStepStatus.WAITING_USER
        state.pending_interaction = PendingInteraction(
            type=PendingInteractionType.CLARIFICATION,
            reason="需要提供或选择一个 Research Artifact，才能生成 Content Strategy。",
            required_fields=["research_artifact_ref"],
            resume_token="CONTENT_STRATEGY_V1_RESUME",
        )
        return self._result(state)

    def _tool_failed(self, state, step, error):
        return self._failed(state, error, step)

    def _failed(self, state, error, step=None):
        state.status = WorkflowStatus.FAILED
        if step:
            state.step_states[step] = ResearchStepStatus.FAILED
        return ContentStrategyWorkflowResult(status=state.status, state=state, warnings=state.warnings, error=error)

    def _result(self, state):
        return ContentStrategyWorkflowResult(
            status=state.status,
            state=state,
            strategy_artifact_ref=state.strategy_artifact_ref,
            generated_opportunity_refs=state.generated_opportunity_refs,
            warnings=state.warnings,
            pending_interaction=state.pending_interaction,
        )

    def _validation_error(self, message):
        return ToolError(code="VALIDATION_ERROR", category="VALIDATION", retryable=False, safe_message=message)
