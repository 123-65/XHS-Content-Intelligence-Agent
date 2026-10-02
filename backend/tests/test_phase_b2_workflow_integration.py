from types import SimpleNamespace

import httpx

from app.agent.context.contracts import StructuredContext
from app.agent.control.current_turn_materials import (
    CurrentMaterialSource,
    CurrentMaterialType,
    NormalizedCurrentMaterial,
)
from app.agent.control.turn_contracts import TurnContextState
from app.agent.conversation_v2.service import ConversationalAgentService
from app.agent.conversation_v2.execution_gate import ExecutionGateReason, ExecutionGateResult, ExecutionMode
from app.agent.conversation_v2.deps import ConversationAgentDeps
from app.agent.conversation_v2.decision_context import CanonicalTurnContextBuilder
from app.agent.conversation_v2.outcomes import TurnExecutionLedger
from app.agent.conversation_v2.capabilities import CAPABILITIES
from app.agent.conversation_v2.workflow_tools import _start, run_content_strategy, run_post_publish_review
from app.agent.conversation_v2.workspace import TrustedWorkspaceBuilder
from app.agent.conversation_v2.workspace import RecentTrustedContext, TrustedWorkspaceSnapshot
from app.agent.schemas.execution import AgentTurnResult, ArtifactRef, ArtifactType, RuntimeAction, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.schemas.semantic import Intent
from app.agent.workflows.definitions import WorkflowId
from app.collectors.xhs.xiaohongshu_mcp_provider import XiaohongshuMcpProvider
from app.llm.errors import LLMTimeoutError
from app.agent.tools.semantic_tools import GenerateContentStrategyTool
from app.agent.tools.execution_context import ToolExecutionContext
from app.schemas.unified_agent import AgentTurnMaterials
from pydantic_ai import ModelRetry
import pytest


class ContextOwnerSpy:
    def __init__(self):
        self.saved = None

    def save(self, conversation_id, account_ref, state):
        self.saved = state


def _service():
    service = ConversationalAgentService.__new__(ConversationalAgentService)
    service.context_owner = ContextOwnerSpy()
    return service


def _result(status, artifacts):
    return AgentTurnResult(
        action=RuntimeAction.EXECUTE_PLAN,
        intent=Intent.RESEARCH,
        message="done",
        artifacts=artifacts,
        status=status,
    )


def test_configured_real_provider_connection_failure_is_environment_blocked():
    def blocked(request):
        raise httpx.ConnectError("network unavailable", request=request)

    provider = XiaohongshuMcpProvider(
        base_url="http://host.docker.internal:18060",
        transport=httpx.MockTransport(blocked),
    )
    result = provider.collect_account(
        "https://www.xiaohongshu.com/user/profile/u1?xsec_token=authorized"
    )
    assert result.status == "ENV_BLOCKED"
    assert result.error_code == "ENV_BLOCKED"
    assert result.provider_name == "xiaohongshu_mcp"
    assert result.is_mock is False


def test_missing_provider_config_remains_explicit_and_has_no_mock_fallback():
    provider = XiaohongshuMcpProvider(base_url="")
    result = provider.collect_account(
        "https://www.xiaohongshu.com/user/profile/u1?xsec_token=authorized"
    )
    assert result.error_code == "PROVIDER_NOT_CONFIGURED"
    assert result.is_mock is False


def test_successful_strategy_saves_ordered_opportunity_collection_for_followup():
    service = _service()
    state = TurnContextState()
    artifacts = [
        ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=44),
        ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=91),
        ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=92),
    ]
    service._save_recent_context(state, StructuredContext(), _result(WorkflowStatus.SUCCESS, artifacts), 7, 3)

    recent = TrustedWorkspaceBuilder.__new__(TrustedWorkspaceBuilder).recent(state.recent_context)
    assert recent.strategy_ref == 44
    assert recent.opportunity_ref == 91
    assert [item.ref.id for item in state.recent_context.opportunity_collections[-1].opportunity_refs] == [91, 92]


def test_failed_workflow_does_not_pollute_recent_artifact_identity():
    service = _service()
    state = TurnContextState()
    artifacts = [ArtifactRef(type=ArtifactType.RESEARCH, id=101)]
    service._save_recent_context(state, StructuredContext(), _result(WorkflowStatus.FAILED, artifacts), 7, 3)
    assert state.recent_context.references == []
    assert state.recent_context.opportunity_collections == []


def test_review_success_saves_review_identity_without_business_object_copy():
    service = _service()
    state = TurnContextState()
    artifacts = [ArtifactRef(type=ArtifactType.POST_PUBLISH_REVIEW, id=303)]
    service._save_recent_context(state, StructuredContext(), _result(WorkflowStatus.SUCCESS, artifacts), 7, 3)
    assert state.recent_context.review_refs == [303]


def test_business_llm_timeout_maps_to_explicit_tool_failure():
    service = SimpleNamespace(generate_semantic=lambda payload: (_ for _ in ()).throw(LLMTimeoutError("timeout")))
    tool = GenerateContentStrategyTool(service=service)
    data = SimpleNamespace(model_dump=lambda **kwargs: {})
    result = tool.execute(data)
    assert result.success is False
    assert result.error.code == "LLM_TIMEOUT"
    assert result.error.category == "TIMEOUT"
    assert "超时" in result.error.safe_message


def test_one_turn_reuses_first_workflow_outcome_without_second_side_effect():
    calls = []

    def start(request, context):
        calls.append(request)
        return SimpleNamespace(
            workflow_name=request.workflow_name.value,
            status=WorkflowStatus.SUCCESS,
            run_ref="run-once",
            checkpoint_version=3,
            result=None,
            pending_interaction=None,
            warnings=[],
            error=None,
        )

    ledger = TurnExecutionLedger()
    ctx = SimpleNamespace(deps=SimpleNamespace(
        turn_execution_ledger=ledger,
        workflow_invoker=SimpleNamespace(start=start),
        execution_context=SimpleNamespace(),
    ))
    payload = {"account_ref": 7}

    first = _start(ctx, "run_content_creation", WorkflowId.CONTENT_CREATION_V1, payload)
    second = _start(ctx, "run_content_creation", WorkflowId.CONTENT_CREATION_V1, payload)

    assert first is second
    assert first.run_ref == "run-once"
    assert len(calls) == 1
    assert ledger.outcomes == [first]


@pytest.mark.parametrize("wrong_tool", [run_content_strategy, run_post_publish_review])
def test_current_external_xhs_material_rejects_non_research_workflow_tools(wrong_tool):
    workspace = TrustedWorkspaceSnapshot(research_ref=11, published_note_ref=592)
    recent = RecentTrustedContext()
    materials = AgentTurnMaterials(profile_urls=["https://www.xiaohongshu.com/user/profile/u1"])
    decision_context = CanonicalTurnContextBuilder().build(
        current_materials=(NormalizedCurrentMaterial(
            material_type=CurrentMaterialType.EXTERNAL_XHS_PROFILE,
            source_url=materials.profile_urls[0],
            source=CurrentMaterialSource.EXPLICIT_MATERIAL,
        ),),
        workspace=workspace,
        recent=recent,
        pending=None,
    )
    deps = ConversationAgentDeps(
        account_ref=7,
        conversation_id=3,
        current_text="比较这些账号",
        runtime=SimpleNamespace(),
        execution_context=ToolExecutionContext(db=None),
        trusted_workspace=workspace,
        recent_context=recent,
        current_materials=materials,
        recent_note_urls=(),
        recent_profile_urls=(),
        capabilities=CAPABILITIES,
        turn_execution_ledger=TurnExecutionLedger(),
        workflow_invoker=SimpleNamespace(),
        execution_gate=ExecutionGateResult(
            mode=ExecutionMode.BUSINESS_ACTION,
            confidence=1,
            reason_code=ExecutionGateReason.EXPLICIT_BUSINESS_ACTION,
        ),
        decision_context=decision_context,
    )
    with pytest.raises(ModelRetry, match="not eligible"):
        wrong_tool(SimpleNamespace(deps=deps), "执行")


def _pending_interaction():
    return PendingInteraction(
        type=PendingInteractionType.CLARIFICATION,
        reason="请补充材料",
        required_fields=["research_material"],
        resume_token="RESEARCH_V1_RESUME",
    )


def test_pending_fact_requires_account_workflow_status_checkpoint_and_material_compatibility():
    service = ConversationalAgentService.__new__(ConversationalAgentService)
    service.runtime = SimpleNamespace(get_run=lambda run_ref: SimpleNamespace(
        run_ref=run_ref,
        workflow_name=WorkflowId.RESEARCH_V1.value,
        account_ref=7,
        status=WorkflowStatus.WAITING_USER,
        checkpoint_version=3,
        pending_interaction=_pending_interaction(),
    ))
    state = TurnContextState(
        active_pending_run_ref="run-pending",
        active_pending_checkpoint_version=3,
        active_pending_interaction=_pending_interaction(),
    )

    pending = service._validated_pending(
        state,
        7,
        frozenset({CurrentMaterialType.EXTERNAL_XHS_PROFILE}),
    )

    assert pending is not None
    assert pending.workflow_type == WorkflowId.RESEARCH_V1
    assert pending.resumable is True
    assert pending.requirements_satisfied is True


@pytest.mark.parametrize(
    "override",
    [
        {"account_ref": 8},
        {"workflow_name": WorkflowId.CONTENT_STRATEGY_V1.value},
        {"status": WorkflowStatus.SUCCESS},
        {"checkpoint_version": 4},
        {"pending_interaction": None},
    ],
)
def test_invalid_pending_runtime_fact_is_not_exposed_as_resumable(override):
    values = {
        "workflow_name": WorkflowId.RESEARCH_V1.value,
        "account_ref": 7,
        "status": WorkflowStatus.WAITING_USER,
        "checkpoint_version": 3,
        "pending_interaction": _pending_interaction(),
    }
    values.update(override)
    service = ConversationalAgentService.__new__(ConversationalAgentService)
    service.runtime = SimpleNamespace(get_run=lambda run_ref: SimpleNamespace(run_ref=run_ref, **values))
    state = TurnContextState(
        active_pending_run_ref="run-pending",
        active_pending_checkpoint_version=3,
        active_pending_interaction=_pending_interaction(),
    )
    assert service._validated_pending(
        state,
        7,
        frozenset({CurrentMaterialType.EXTERNAL_XHS_PROFILE}),
    ) is None


