from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.access_scopes import EvidenceAccessScope, RunLocalEvidenceGrant
from app.agent.tools.artifact_contracts import CreateResearchArtifactInput
from app.agent.tools.definitions import ToolError, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import build_tool_handler
from app.agent.tools.query_contracts import (
    EvidenceBundle,
    GrowthContextSection,
    QueryArtifactInput,
    QueryGrowthContextInput,
    RetrieveResearchEvidenceInput,
)
from app.agent.tools.semantic_contracts import AnalyzeResearchInput
from app.agent.tools.xhs_contracts import CollectXhsAccountsInput, CollectXhsNotesInput, NoteCollectionPurpose
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.registry import get_workflow
from app.analysis.competitor.evidence_adapter import CompetitorEvidenceAdapter
from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult


class ResearchWorkflowInput(BaseModel):
    """RESEARCH_V1 的纯业务输入，不接受可信执行对象或 Workflow State。"""

    model_config = ConfigDict(extra="forbid")
    account_ref: int = Field(gt=0)
    research_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    note_urls: list[str] = Field(default_factory=list)
    profile_urls: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


class ResearchStepStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    WAITING_USER = "WAITING_USER"
    FAILED = "FAILED"


STEP_IDS = (
    "growth_context", "artifact_context", "collection_accounts", "collection_notes",
    "evidence_retrieval", "evidence_adapter", "evidence_gate", "analysis", "artifact_creation",
)


class ResearchWorkflowState(BaseModel):
    """服务器内部、可序列化的 RESEARCH_V1 逻辑恢复状态。"""

    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus = WorkflowStatus.PENDING
    account_ref: int
    research_goal: str
    constraints: list[str] = Field(default_factory=list)
    growth_context: dict | None = None
    resolved_artifacts: list[dict] = Field(default_factory=list)
    resolved_artifact_keys: list[str] = Field(default_factory=list)
    requested_evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    collected_note_refs: list[int] = Field(default_factory=list)
    collected_account_refs: list[int] = Field(default_factory=list)
    run_local_evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    retrieved_ref_keys: list[str] = Field(default_factory=list)
    retrieved_evidence: EvidenceBundle | None = None
    competitor_evidence: CompetitorEvidence | None = None
    warnings: list[str] = Field(default_factory=list)
    analysis_result: CompetitorSemanticResult | None = None
    research_artifact_ref: ArtifactRef | None = None
    pending_interaction: PendingInteraction | None = None
    step_states: dict[str, ResearchStepStatus] = Field(
        default_factory=lambda: {step: ResearchStepStatus.NOT_STARTED for step in STEP_IDS}
    )
    processed_note_urls: list[str] = Field(default_factory=list)
    processed_profile_urls: list[str] = Field(default_factory=list)


class ResearchWorkflowResult(BaseModel):
    """Workflow 状态、稳定 Artifact Ref 与失败信息的统一返回。"""

    model_config = ConfigDict(extra="forbid")
    status: WorkflowStatus
    state: ResearchWorkflowState
    research_artifact_ref: ArtifactRef | None = None
    warnings: list[str] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    error: ToolError | None = None


class ResearchWorkflow:
    """只编排冻结 Tool 和唯一 Evidence Adapter 的确定性 RESEARCH_V1。"""

    workflow_id = WorkflowId.RESEARCH_V1

    def __init__(self, adapter: CompetitorEvidenceAdapter | None = None):
        self.adapter = adapter or CompetitorEvidenceAdapter()
        self.allowlist = frozenset(get_workflow(self.workflow_id).allowed_tools)

    def execute(self, data: ResearchWorkflowInput, context: ToolExecutionContext) -> ResearchWorkflowResult:
        state = ResearchWorkflowState(
            account_ref=data.account_ref,
            research_goal=data.research_goal,
            constraints=data.constraints,
            requested_evidence_refs=list(data.evidence_refs),
        )
        return self._run(state, data, context)

    def resume(self, state: ResearchWorkflowState, data: ResearchWorkflowInput, context: ToolExecutionContext) -> ResearchWorkflowResult:
        if data.account_ref != state.account_ref:
            return self._failed(state, ToolError(code="VALIDATION_ERROR", category="VALIDATION", retryable=False, safe_message="Resume account_ref 不一致。"))
        if state.research_artifact_ref is not None:
            state.status = WorkflowStatus.PARTIAL_SUCCESS if state.warnings else WorkflowStatus.SUCCESS
            return self._result(state)
        state.pending_interaction = None
        state.research_goal = data.research_goal
        state.constraints = list(dict.fromkeys([*state.constraints, *data.constraints]))
        state.requested_evidence_refs = self._dedupe_refs([*state.requested_evidence_refs, *data.evidence_refs])
        return self._run(state, data, context)

    def _run(self, state, data, context):
        state.status = WorkflowStatus.RUNNING
        if state.growth_context is None:
            result = self._call(ToolName.QUERY_GROWTH_CONTEXT, QueryGrowthContextInput(
                account_ref=state.account_ref, requested_sections=list(GrowthContextSection)
            ), context, retry=True)
            if not result.success:
                return self._tool_failed(state, "growth_context", result.error)
            state.growth_context = result.data.model_dump(mode="json")
            state.step_states["growth_context"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["growth_context"] = ResearchStepStatus.SKIPPED

        for ref in data.artifact_refs:
            key = f"{ref.type}:{ref.id}"
            if key in state.resolved_artifact_keys:
                continue
            result = self._call(ToolName.QUERY_ARTIFACT, QueryArtifactInput(account_ref=state.account_ref, artifact_ref=ref), context, retry=True)
            if not result.success:
                return self._tool_failed(state, "artifact_context", result.error)
            state.resolved_artifacts.append(result.data.model_dump(mode="json"))
            state.resolved_artifact_keys.append(key)
        state.step_states["artifact_context"] = ResearchStepStatus.SUCCESS if data.artifact_refs else ResearchStepStatus.SKIPPED

        current_collection_results = []
        new_profiles = [url for url in data.profile_urls if url not in state.processed_profile_urls]
        if new_profiles:
            result = self._call(ToolName.COLLECT_XHS_ACCOUNTS, CollectXhsAccountsInput(workspace_account_ref=state.account_ref, profile_urls=new_profiles), context, retry=True)
            if not result.success:
                return self._tool_failed(state, "collection_accounts", result.error)
            current_collection_results.append(result)
            state.processed_profile_urls.extend(new_profiles)
            state.collected_account_refs.extend(item.account_ref for item in result.data.items)
            self._warnings(state, result.warnings)
            state.step_states["collection_accounts"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["collection_accounts"] = ResearchStepStatus.SKIPPED

        new_notes = [url for url in data.note_urls if url not in state.processed_note_urls]
        if new_notes:
            result = self._call(ToolName.COLLECT_XHS_NOTES, CollectXhsNotesInput(
                account_ref=state.account_ref, note_urls=new_notes, collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT
            ), context, retry=True)
            if not result.success:
                return self._tool_failed(state, "collection_notes", result.error)
            current_collection_results.append(result)
            state.processed_note_urls.extend(new_notes)
            state.collected_note_refs.extend(item.note_ref for item in result.data.items)
            self._warnings(state, result.warnings)
            state.step_states["collection_notes"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["collection_notes"] = ResearchStepStatus.SKIPPED

        grants = [RunLocalEvidenceGrant.from_successful_collection_result(item) for item in current_collection_results]
        new_collected_refs = self._dedupe_refs([ref for grant in grants for ref in grant.trusted_collected_refs])
        state.run_local_evidence_refs = self._dedupe_refs([*state.run_local_evidence_refs, *new_collected_refs])
        pending_refs = [ref for ref in self._dedupe_refs([*state.requested_evidence_refs, *new_collected_refs]) if self._ref_key(ref) not in state.retrieved_ref_keys]

        if pending_refs:
            collected_keys = {self._ref_key(ref) for ref in new_collected_refs}
            external_refs = context.evidence_access_scope.authorized_refs if context.evidence_access_scope else frozenset()
            unauthorized = [ref for ref in pending_refs if self._ref_key(ref) not in collected_keys and ref not in external_refs]
            if unauthorized:
                return self._failed(state, ToolError(code="PERMISSION_ERROR", category="PERMISSION", retryable=False, safe_message="历史 EvidenceRef 未获得外部授权。"), "evidence_retrieval")
            effective = context.evidence_access_scope
            for grant in grants:
                effective = effective.with_run_local_grant(grant) if effective else EvidenceAccessScope.from_run_local_grant(grant)
            retrieval_context = ToolExecutionContext(db=context.db, evidence_access_scope=effective, collection_access_scope=context.collection_access_scope)
            result = self._call(ToolName.RETRIEVE_RESEARCH_EVIDENCE, RetrieveResearchEvidenceInput(
                account_ref=state.account_ref, evidence_refs=pending_refs, purpose=state.research_goal
            ), retrieval_context, retry=True)
            if not result.success:
                return self._tool_failed(state, "evidence_retrieval", result.error)
            state.retrieved_evidence = self._merge_bundles(state.retrieved_evidence, result.data)
            state.retrieved_ref_keys.extend(self._ref_key(ref) for ref in pending_refs)
            state.step_states["evidence_retrieval"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["evidence_retrieval"] = ResearchStepStatus.SKIPPED

        if state.retrieved_evidence is None or not state.retrieved_evidence.items:
            return self._waiting(state)
        try:
            state.competitor_evidence = self.adapter.from_bundle(state.retrieved_evidence)
            state.step_states["evidence_adapter"] = ResearchStepStatus.SUCCESS
        except Exception:
            return self._failed(state, ToolError(code="ADAPTER_ERROR", category="VALIDATION", retryable=False, safe_message="Research Evidence 转换失败。"), "evidence_adapter")
        if not state.competitor_evidence.notes:
            return self._waiting(state)
        state.step_states["evidence_gate"] = ResearchStepStatus.SUCCESS
        if len(state.competitor_evidence.notes) < 3:
            self._warnings(state, ["INSUFFICIENT_SAMPLE"])
        if len(state.competitor_evidence.comments) < 3:
            self._warnings(state, ["INSUFFICIENT_COMMENT_SAMPLE"])

        if state.analysis_result is None:
            analysis = self._call(ToolName.ANALYZE_RESEARCH, AnalyzeResearchInput(
                account_ref=state.account_ref, growth_context=state.growth_context,
                evidence_bundle=state.competitor_evidence, research_goal=state.research_goal,
                constraints=state.constraints, source_refs=data.artifact_refs,
            ), context, retry=False)
            if not analysis.success:
                return self._tool_failed(state, "analysis", analysis.error)
            state.analysis_result = analysis.data
            state.step_states["analysis"] = ResearchStepStatus.SUCCESS
        else:
            state.step_states["analysis"] = ResearchStepStatus.SKIPPED
        if state.research_artifact_ref is None:
            artifact = self._call(ToolName.CREATE_RESEARCH_ARTIFACT, CreateResearchArtifactInput(
                account_ref=state.account_ref, research_result=state.analysis_result,
                research_evidence=state.competitor_evidence, source_refs=data.artifact_refs,
                report_name=state.research_goal[:128], sample_state={"data_quality": "PARTIAL" if state.warnings else "READY"},
            ), context, retry=False)
            if not artifact.success:
                return self._tool_failed(state, "artifact_creation", artifact.error)
            state.research_artifact_ref = artifact.data.artifact_ref
            state.step_states["artifact_creation"] = ResearchStepStatus.SUCCESS
        state.status = WorkflowStatus.PARTIAL_SUCCESS if state.warnings else WorkflowStatus.SUCCESS
        return self._result(state)

    def _call(self, name, payload, context, retry):
        if name not in self.allowlist:
            raise ValueError(f"RESEARCH_V1 Tool 越权: {name}")
        handler = build_tool_handler(name, context)
        result = handler.execute(payload)
        if retry and not result.success and result.error and result.error.retryable:
            result = handler.execute(payload)
        return result

    def _waiting(self, state):
        state.status = WorkflowStatus.WAITING_USER
        state.step_states["evidence_gate"] = ResearchStepStatus.WAITING_USER
        state.pending_interaction = PendingInteraction(
            type=PendingInteractionType.CLARIFICATION,
            reason="请提供要分析的小红书账号或笔记链接。",
            required_fields=["research_material"], resume_token="RESEARCH_V1_RESUME",
        )
        return self._result(state)

    def _tool_failed(self, state, step, error):
        return self._failed(state, error, step)

    def _failed(self, state, error, step=None):
        state.status = WorkflowStatus.FAILED
        if step:
            state.step_states[step] = ResearchStepStatus.FAILED
        return ResearchWorkflowResult(status=state.status, state=state, warnings=state.warnings, error=error)

    def _result(self, state):
        return ResearchWorkflowResult(status=state.status, state=state, research_artifact_ref=state.research_artifact_ref, warnings=state.warnings, pending_interaction=state.pending_interaction)

    def _warnings(self, state, warnings):
        state.warnings = list(dict.fromkeys([*state.warnings, *warnings]))

    def _merge_bundles(self, existing, current):
        if existing is None:
            return current
        keys = {(item.evidence_type, item.evidence_ref.id) for item in existing.items}
        items = [*existing.items, *(item for item in current.items if (item.evidence_type, item.evidence_ref.id) not in keys)]
        return EvidenceBundle(items=items, purpose=current.purpose, truncated=existing.truncated or current.truncated)

    def _dedupe_refs(self, refs):
        return list({self._ref_key(ref): ref for ref in refs}.values())

    def _ref_key(self, ref):
        return f"{ref.type}:{ref.id}"
