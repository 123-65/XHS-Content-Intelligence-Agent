from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.artifact_contracts import (
    CreatePostPublishReviewArtifactInput,
    CreateStrategyCandidateInput,
)
from app.agent.tools.definitions import ToolError, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import build_tool_handler
from app.agent.tools.query_contracts import (
    ContentOpportunityArtifactView,
    ContentStrategyArtifactView,
    DraftArtifactView,
    GrowthContextSection,
    GrowthContextResult,
    PostPublishMetricsResult,
    QueryArtifactInput,
    QueryGrowthContextInput,
    QueryPostPublishMetricsInput,
)
from app.agent.tools.semantic_contracts import AnalyzePostPublishReviewInput
from app.agent.tools.xhs_contracts import CollectXhsNotesInput, NoteCollectionPurpose
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.registry import get_workflow
from app.agent.workflows.research import ResearchStepStatus
from app.schemas.content_strategy import EvidenceRef
from app.schemas.publication import PostPublishReviewLLMResult


STEP_IDS = (
    "growth_context",
    "metrics",
    "published_draft",
    "strategy",
    "opportunity",
    "metrics_refresh",
    "analysis",
    "review_persistence",
    "candidate_persistence",
)


class PostPublishReviewWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_ref: int = Field(gt=0)
    published_note_ref: int | None = Field(default=None, gt=0)
    window_start: datetime
    window_end: datetime
    refresh_public_metrics: bool = False
    include_private_metrics: bool = True


class PostPublishReviewWorkflowState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: WorkflowStatus = WorkflowStatus.PENDING
    account_ref: int
    published_note_ref: int | None = None
    window_start: datetime
    window_end: datetime
    refresh_public_metrics: bool = False
    include_private_metrics: bool = True
    growth_context: GrowthContextResult | None = None
    metrics: PostPublishMetricsResult | None = None
    published_draft: DraftArtifactView | None = None
    strategy: ContentStrategyArtifactView | None = None
    opportunity: ContentOpportunityArtifactView | None = None
    analysis: PostPublishReviewLLMResult | None = None
    review_artifact_ref: int | None = None
    candidate_refs_by_index: dict[int, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    step_states: dict[str, ResearchStepStatus] = Field(
        default_factory=lambda: {step: ResearchStepStatus.NOT_STARTED for step in STEP_IDS}
    )


class PostPublishReviewWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: WorkflowStatus
    state: PostPublishReviewWorkflowState
    review_artifact_ref: int | None = None
    candidate_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    error: ToolError | None = None


class PostPublishReviewWorkflow:
    workflow_id = WorkflowId.POST_PUBLISH_REVIEW_V1

    def __init__(self):
        self.allowlist = frozenset(get_workflow(self.workflow_id).allowed_tools)

    def execute(self, data: PostPublishReviewWorkflowInput, context: ToolExecutionContext):
        state = PostPublishReviewWorkflowState(**data.model_dump())
        return self._run(state, context)

    def resume(self, state: PostPublishReviewWorkflowState, data: PostPublishReviewWorkflowInput, context: ToolExecutionContext):
        if data.account_ref != state.account_ref or (
            state.published_note_ref is not None
            and data.published_note_ref not in (None, state.published_note_ref)
        ):
            return self._failed(state, self._error("VALIDATION_ERROR", "Resume 不允许更换账号或 Published Note。"))
        if state.published_note_ref is None:
            state.published_note_ref = data.published_note_ref
        state.window_start, state.window_end = data.window_start, data.window_end
        state.refresh_public_metrics = data.refresh_public_metrics
        state.include_private_metrics = data.include_private_metrics
        state.pending_interaction = None
        return self._run(state, context)

    def _run(self, state, context):
        state.status = WorkflowStatus.RUNNING
        if state.published_note_ref is None:
            return self._waiting(state, ["published_note_ref"], "请提供需要复盘的 Published Note。")

        if state.review_artifact_ref is not None and state.analysis is not None:
            return self._persist_candidates(state, context)

        growth = self._call(
            ToolName.QUERY_GROWTH_CONTEXT,
            QueryGrowthContextInput(
                account_ref=state.account_ref,
                requested_sections=list(GrowthContextSection),
            ),
            context,
            retry=True,
        )
        if not growth.success:
            return self._failed(state, growth.error, "growth_context")
        state.growth_context = growth.data
        state.step_states["growth_context"] = ResearchStepStatus.SUCCESS

        metrics_result = self._query_metrics(state, context)
        if not metrics_result.success:
            return self._failed(state, metrics_result.error, "metrics")
        state.metrics = metrics_result.data
        state.step_states["metrics"] = ResearchStepStatus.SUCCESS
        lineage_error = self._validate_metrics_lineage(state)
        if lineage_error:
            return self._failed(state, lineage_error, "metrics")

        draft_result = self._call(
            ToolName.QUERY_ARTIFACT,
            QueryArtifactInput(
                account_ref=state.account_ref,
                artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=state.metrics.draft_ref),
                expected_type=ArtifactType.DRAFT,
                draft_version_ref=state.metrics.published_draft_version_ref,
            ),
            context,
            retry=True,
        )
        if not draft_result.success:
            return self._failed(state, draft_result.error, "published_draft")
        state.published_draft = DraftArtifactView.model_validate(draft_result.data.content)
        if state.published_draft.account_ref != state.account_ref:
            return self._failed(state, self._error("PERMISSION_ERROR", "Published Draft 不属于当前账号。", "PERMISSION"), "published_draft")
        if (
            state.published_draft.resolved_draft_version_ref != state.metrics.published_draft_version_ref
            or state.published_draft.resolved_content is None
            or state.published_draft.strategy_artifact_ref is None
            or state.published_draft.opportunity_ref is None
        ):
            return self._failed(state, self._error("DRAFT_LINEAGE_MISMATCH", "Published Draft Version lineage 不一致。"), "published_draft")
        state.step_states["published_draft"] = ResearchStepStatus.SUCCESS

        resolved = self._resolve_strategy_lineage(state, context)
        if resolved is not None:
            return resolved

        if state.refresh_public_metrics:
            refresh_error = self._refresh_metrics(state, context)
            if refresh_error is not None:
                if isinstance(refresh_error, PostPublishReviewWorkflowResult):
                    return refresh_error
                if self._has_public_metrics(state.metrics):
                    self._warn(state, "PUBLIC_METRICS_REFRESH_FAILED")
                else:
                    self._warn(state, "PUBLIC_METRICS_UNKNOWN")

        if not self._has_public_metrics(state.metrics):
            self._warn(state, "PUBLIC_METRICS_UNKNOWN")
        if not self._has_complete_private_metrics(state.metrics):
            self._warn(state, "PRIVATE_METRICS_UNKNOWN")

        if state.analysis is None:
            analysis = self._call(
                ToolName.ANALYZE_POST_PUBLISH_REVIEW,
                AnalyzePostPublishReviewInput(
                    published_note={
                        "published_note_ref": state.metrics.published_note_ref,
                        "publish_url": state.metrics.publish_url,
                        "draft_ref": state.metrics.draft_ref,
                    },
                    published_draft=state.published_draft.resolved_content.model_dump(),
                    content_strategy=state.strategy.model_dump(),
                    opportunity=state.opportunity.model_dump(),
                    metrics=state.metrics,
                    grounding_refs=self._grounding_refs(state),
                    historical_context=state.growth_context.strategy_memory,
                ),
                context,
                retry=False,
            )
            if not analysis.success:
                return self._failed(state, analysis.error, "analysis")
            state.analysis = analysis.data
            state.step_states["analysis"] = ResearchStepStatus.SUCCESS

        if state.review_artifact_ref is None:
            grounding_refs = self._grounding_refs(state)
            metric_refs = [ref for ref in grounding_refs if ref.kind in {"public_metric_snapshot", "private_metric_snapshot"}]
            persistence = self._call(
                ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT,
                CreatePostPublishReviewArtifactInput(
                    account_ref=state.account_ref,
                    published_note_ref=state.published_note_ref,
                    draft_ref=state.metrics.draft_ref,
                    strategy_ref=state.published_draft.strategy_artifact_ref,
                    opportunity_ref=state.published_draft.opportunity_ref,
                    review_result=state.analysis,
                    metric_snapshot_refs=metric_refs,
                    evidence_refs=grounding_refs,
                ),
                context,
                retry=False,
            )
            if not persistence.success:
                return self._failed(state, persistence.error, "review_persistence")
            state.review_artifact_ref = persistence.data.artifact_ref.id
            state.step_states["review_persistence"] = ResearchStepStatus.SUCCESS
        return self._persist_candidates(state, context)

    def _resolve_strategy_lineage(self, state, context):
        for step, artifact_type, artifact_id, view_type in (
            ("strategy", ArtifactType.CONTENT_STRATEGY, state.published_draft.strategy_artifact_ref, ContentStrategyArtifactView),
            ("opportunity", ArtifactType.CONTENT_OPPORTUNITY, state.published_draft.opportunity_ref, ContentOpportunityArtifactView),
        ):
            result = self._call(ToolName.QUERY_ARTIFACT, QueryArtifactInput(
                account_ref=state.account_ref,
                artifact_ref=ArtifactRef(type=artifact_type, id=artifact_id),
                expected_type=artifact_type,
            ), context, retry=True)
            if not result.success:
                return self._failed(state, result.error, step)
            value = view_type.model_validate(result.data.content)
            if value.account_ref != state.account_ref:
                return self._failed(state, self._error("PERMISSION_ERROR", f"{step} 不属于当前账号。", "PERMISSION"), step)
            setattr(state, step, value)
            state.step_states[step] = ResearchStepStatus.SUCCESS
        if state.opportunity.strategy_artifact_ref != state.published_draft.strategy_artifact_ref:
            return self._failed(state, self._error("DRAFT_LINEAGE_MISMATCH", "Opportunity 与 Published Draft Strategy lineage 不一致。"), "opportunity")
        return None

    def _refresh_metrics(self, state, context):
        if not state.metrics.publish_url:
            return self._failed(state, self._error("PUBLISHED_URL_MISSING", "Published Note 缺少持久化 publish_url。"), "metrics_refresh")
        scope = context.collection_access_scope
        if scope is None or scope.published_note_ref != state.published_note_ref or state.metrics.publish_url not in scope.allowed_note_urls:
            return self._failed(state, self._error("PERMISSION_ERROR", "Published Note 刷新范围不匹配。", "PERMISSION"), "metrics_refresh")
        refreshed = self._call(ToolName.COLLECT_XHS_NOTES, CollectXhsNotesInput(
            account_ref=state.account_ref,
            note_urls=[state.metrics.publish_url],
            collection_purpose=NoteCollectionPurpose.REFRESH_BOUND_PUBLISHED_NOTE,
        ), context, retry=True)
        if not refreshed.success:
            return refreshed.error
        for warning in refreshed.warnings:
            self._warn(state, warning)
        state.step_states["metrics_refresh"] = ResearchStepStatus.SUCCESS
        requeried = self._query_metrics(state, context)
        if not requeried.success:
            return requeried.error
        state.metrics = requeried.data
        return None

    def _persist_candidates(self, state, context):
        failed = False
        for candidate in state.analysis.strategy_candidates:
            index = candidate.candidate_index
            if index in state.candidate_refs_by_index:
                continue
            result = self._call(ToolName.CREATE_STRATEGY_CANDIDATE, CreateStrategyCandidateInput(
                account_ref=state.account_ref,
                post_publish_review_ref=state.review_artifact_ref,
                candidate=candidate,
            ), context, retry=False)
            if not result.success:
                failed = True
                break
            state.candidate_refs_by_index[index] = result.data.strategy_candidate_ref
        if failed:
            self._warn(state, "STRATEGY_CANDIDATE_PERSIST_PARTIAL")
        elif "STRATEGY_CANDIDATE_PERSIST_PARTIAL" in state.warnings:
            state.warnings.remove("STRATEGY_CANDIDATE_PERSIST_PARTIAL")
        state.step_states["candidate_persistence"] = ResearchStepStatus.FAILED if failed else ResearchStepStatus.SUCCESS
        state.status = WorkflowStatus.PARTIAL_SUCCESS if state.warnings else WorkflowStatus.SUCCESS
        return self._result(state)

    def _query_metrics(self, state, context):
        return self._call(ToolName.QUERY_POST_PUBLISH_METRICS, QueryPostPublishMetricsInput(
            account_ref=state.account_ref,
            published_note_ref=state.published_note_ref,
            window_start=state.window_start,
            window_end=state.window_end,
            include_private=state.include_private_metrics,
        ), context, retry=True)

    def _validate_metrics_lineage(self, state):
        metrics = state.metrics
        if metrics.published_note_ref != state.published_note_ref:
            return self._error("PUBLISHED_NOTE_MISMATCH", "指标不属于当前 Published Note。")
        if metrics.account_ref != state.account_ref:
            return self._error("PERMISSION_ERROR", "Published Note 不属于当前账号。", "PERMISSION")
        if not metrics.published_lineage_complete or metrics.published_draft_version_ref is None or metrics.draft_ref is None:
            return self._error("PUBLISHED_VERSION_LINEAGE_MISSING", "Published Note 缺少精确 Draft Version lineage。")
        return None

    @staticmethod
    def _grounding_refs(state) -> list[EvidenceRef]:
        """仅传播本次 Review 已解析且授权的 canonical grounding refs。"""
        refs = [EvidenceRef(kind="published_note", id=state.metrics.published_note_ref)]
        if state.metrics.public_metric_snapshot_ref is not None:
            refs.append(EvidenceRef(kind="public_metric_snapshot", id=state.metrics.public_metric_snapshot_ref))
        if state.metrics.private_metric_snapshot_ref is not None:
            refs.append(EvidenceRef(kind="private_metric_snapshot", id=state.metrics.private_metric_snapshot_ref))
        refs.extend(state.strategy.evidence_refs)
        for direction in state.strategy.content_directions:
            refs.extend(direction.evidence_refs)
        refs.extend(state.opportunity.opportunity.evidence_refs)

        unique = {}
        for ref in refs:
            unique[(ref.kind, ref.id)] = ref
        return list(unique.values())

    @staticmethod
    def _has_public_metrics(metrics):
        return bool(metrics and metrics.public_metrics and any(item.value is not None for item in metrics.public_metrics.values()))

    @staticmethod
    def _has_complete_private_metrics(metrics):
        return bool(metrics.private_metrics) and all(item.value is not None for item in metrics.private_metrics.values())

    def _call(self, name, payload, context, retry):
        if name not in self.allowlist:
            raise ValueError(f"POST_PUBLISH_REVIEW_V1 Tool 越权: {name}")
        handler = build_tool_handler(name, context)
        result = handler.execute(payload)
        if retry and not result.success and result.error and result.error.retryable:
            result = handler.execute(payload)
        return result

    def _waiting(self, state, fields, reason):
        state.status = WorkflowStatus.WAITING_USER
        state.pending_interaction = PendingInteraction(
            type=PendingInteractionType.CLARIFICATION,
            reason=reason,
            required_fields=fields,
            resume_token="POST_PUBLISH_REVIEW_V1_RESUME",
        )
        return self._result(state)

    def _failed(self, state, error, step=None):
        state.status = WorkflowStatus.FAILED
        if step:
            state.step_states[step] = ResearchStepStatus.FAILED
        return PostPublishReviewWorkflowResult(
            status=state.status,
            state=state,
            review_artifact_ref=state.review_artifact_ref,
            candidate_refs=self._candidate_refs(state),
            warnings=state.warnings,
            error=error,
        )

    def _result(self, state):
        return PostPublishReviewWorkflowResult(
            status=state.status,
            state=state,
            review_artifact_ref=state.review_artifact_ref,
            candidate_refs=self._candidate_refs(state),
            warnings=state.warnings,
            pending_interaction=state.pending_interaction,
        )

    @staticmethod
    def _candidate_refs(state):
        return [state.candidate_refs_by_index[index] for index in sorted(state.candidate_refs_by_index)]

    @staticmethod
    def _warn(state, warning):
        if warning not in state.warnings:
            state.warnings.append(warning)

    @staticmethod
    def _error(code, message, category="VALIDATION"):
        return ToolError(code=code, category=category, retryable=False, safe_message=message)
