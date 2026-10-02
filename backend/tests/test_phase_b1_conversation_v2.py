import inspect
from types import SimpleNamespace

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.test import TestModel

from app.agent.context.contracts import ObjectRef, ResolvedObjectType, StructuredContext, TrustedContextRef
from app.agent.control.current_turn_materials import (
    CurrentMaterialSource,
    CurrentMaterialType,
    NormalizedCurrentMaterial,
)
from app.agent.conversation_v2.agent import build_conversation_agent
from app.agent.conversation_v2.capabilities import CAPABILITIES
from app.agent.conversation_v2.decision_context import CanonicalTurnContextBuilder, PendingFact
from app.agent.conversation_v2.deps import ConversationAgentDeps
from app.agent.conversation_v2.execution_gate import (
    ExecutionGateReason,
    ExecutionGateResult,
    ExecutionMode,
)
from app.agent.conversation_v2.history import ConversationHistoryLoader
from app.agent.conversation_v2.outcomes import (
    ConversationResponse,
    ConversationResponseKind,
    TurnExecutionLedger,
    WorkflowToolOutcome,
)
from app.agent.conversation_v2.response_mapper import ConversationResponseMapper
from app.agent.conversation_v2.workflow_tools import (
    run_content_creation,
    run_content_refinement,
    run_content_strategy,
    run_post_publish_review,
    run_research,
)
from app.agent.conversation_v2.workspace import RecentTrustedContext, TrustedWorkspaceBuilder, TrustedWorkspaceSnapshot
from app.agent.schemas.execution import ArtifactType, RuntimeAction, WorkflowStatus
from app.agent.schemas.semantic import Intent
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.workflows.definitions import WorkflowId
from app.schemas.unified_agent import AgentTurnMaterials


class FakeConversationRepo:
    def __init__(self, rows, account_id=7):
        self.rows = rows
        self.account_id = account_id
        self.before_id = None
        self.limit = None

    def get(self, conversation_id):
        return SimpleNamespace(id=conversation_id, account_id=self.account_id)

    def list_messages(self, conversation_id, limit=30, before_id=None):
        self.before_id = before_id
        self.limit = limit
        eligible = [row for row in self.rows if row.id < before_id]
        return eligible[-limit:]


def _loader(rows, account_id=7):
    loader = ConversationHistoryLoader.__new__(ConversationHistoryLoader)
    loader.repo = FakeConversationRepo(rows, account_id)
    return loader


def _row(row_id, role, content):
    return SimpleNamespace(id=row_id, role=role, content=content)


def test_history_loads_user_and_assistant_visible_text_in_order():
    loader = _loader([_row(1, "USER", "一"), _row(2, "ASSISTANT", "二"), _row(3, "USER", "当前")])
    history = loader.load(conversation_id=1, account_ref=7, before_message_id=3)
    assert isinstance(history.messages[0], ModelRequest)
    assert isinstance(history.messages[0].parts[0], UserPromptPart)
    assert isinstance(history.messages[1], ModelResponse)
    assert isinstance(history.messages[1].parts[0], TextPart)
    assert [item.parts[0].content for item in history.messages] == ["一", "二"]


def test_history_excludes_current_user_message():
    loader = _loader([_row(1, "USER", "旧"), _row(2, "USER", "当前")])
    history = loader.load(conversation_id=1, account_ref=7, before_message_id=2)
    assert [item.parts[0].content for item in history.messages] == ["旧"]
    assert loader.repo.before_id == 2


def test_history_is_limited_to_twenty_messages():
    rows = [_row(index, "USER", str(index)) for index in range(1, 24)]
    history = _loader(rows).load(conversation_id=1, account_ref=7, before_message_id=24, limit=99)
    assert len(history.messages) == 20
    assert history.messages[0].parts[0].content == "4"


def test_history_enforces_account_isolation():
    with pytest.raises(ValueError, match="CONVERSATION_ACCOUNT_MISMATCH"):
        _loader([], account_id=8).load(conversation_id=1, account_ref=7, before_message_id=2)


class FakeInvoker:
    def __init__(self, status=WorkflowStatus.SUCCESS, result=None, error=None):
        self.calls = []
        self.resume_calls = []
        self.status = status
        self.result = result or {}
        self.error = error

    def start(self, request, execution_context):
        self.calls.append((request, execution_context))
        return SimpleNamespace(
            workflow_name=request.workflow_name.value,
            status=self.status,
            run_ref="run-7",
            checkpoint_version=2,
            pending_interaction=None,
            result=self.result,
            warnings=[],
            error=self.error,
        )

    def resume(self, request, execution_context):
        self.resume_calls.append((request, execution_context))
        return SimpleNamespace(
            workflow_name=WorkflowId.RESEARCH_V1.value,
            status=self.status,
            run_ref=request.run_ref,
            checkpoint_version=request.expected_checkpoint_version + 1,
            pending_interaction=None,
            result=self.result,
            warnings=[],
            error=self.error,
        )


def _deps(*, workspace=None, materials=None, recent=None, invoker=None, gate=None):
    invoker = invoker or FakeInvoker()
    workspace = workspace or TrustedWorkspaceSnapshot()
    materials = materials or AgentTurnMaterials()
    recent = recent or RecentTrustedContext()
    normalized_items = tuple(
        [
            NormalizedCurrentMaterial(
                material_type=CurrentMaterialType.EXTERNAL_XHS_NOTE,
                source_url=url,
                source=CurrentMaterialSource.EXPLICIT_MATERIAL,
            )
            for url in materials.note_urls
        ]
        + [
            NormalizedCurrentMaterial(
                material_type=CurrentMaterialType.EXTERNAL_XHS_PROFILE,
                source_url=url,
                source=CurrentMaterialSource.EXPLICIT_MATERIAL,
            )
            for url in materials.profile_urls
        ]
    )
    decision_context = CanonicalTurnContextBuilder().build(
        current_materials=normalized_items,
        workspace=workspace,
        recent=recent,
        pending=None,
    )
    return ConversationAgentDeps(
        account_ref=7,
        conversation_id=3,
        current_text="执行测试任务",
        runtime=SimpleNamespace(),
        execution_context=ToolExecutionContext(db=None),
        trusted_workspace=workspace,
        recent_context=recent,
        current_materials=materials,
        recent_note_urls=(),
        recent_profile_urls=(),
        capabilities=CAPABILITIES,
        turn_execution_ledger=TurnExecutionLedger(),
        workflow_invoker=invoker,
        execution_gate=gate or ExecutionGateResult(
            mode=ExecutionMode.BUSINESS_ACTION,
            confidence=1,
            reason_code=ExecutionGateReason.EXPLICIT_BUSINESS_ACTION,
        ),
        decision_context=decision_context,
    )


def _ctx(deps):
    return SimpleNamespace(deps=deps)


@pytest.mark.parametrize("tool", [run_research, run_content_strategy, run_content_creation, run_content_refinement, run_post_publish_review])
def test_high_level_tools_do_not_accept_account_or_object_identity_from_model(tool):
    parameters = inspect.signature(tool).parameters
    assert list(parameters) in (["ctx", "goal"], ["ctx", "instruction"])
    assert not {"account_ref", "draft_ref", "research_ref", "strategy_ref", "opportunity_ref", "published_note_ref"} & set(parameters)


def test_external_note_and_profile_materials_are_available_to_agent_deps():
    note = "https://www.xiaohongshu.com/explore/abc?xsec_token=keep"
    profile = "https://www.xiaohongshu.com/user/profile/user-a?xsec_token=keep"
    deps = _deps(materials=AgentTurnMaterials(note_urls=[note], profile_urls=[profile]))
    assert deps.current_materials.note_urls == [note]
    assert deps.current_materials.profile_urls == [profile]


def test_opportunity_derives_verified_strategy_lineage():
    builder = TrustedWorkspaceBuilder.__new__(TrustedWorkspaceBuilder)
    builder.strategies = SimpleNamespace(
        get_opportunity=lambda ref: SimpleNamespace(id=ref, strategy_artifact_id=44),
        get_strategy_artifact=lambda ref: SimpleNamespace(id=ref, account_id=7),
    )
    selection = StructuredContext(references=[TrustedContextRef(
        ref=ObjectRef(type=ResolvedObjectType.CONTENT_OPPORTUNITY, id=9), account_ref=7
    )])
    snapshot = builder.build(selection)
    assert snapshot.opportunity_ref == 9
    assert snapshot.opportunity_strategy_ref == 44


def test_opportunity_rejects_cross_account_strategy_lineage():
    builder = TrustedWorkspaceBuilder.__new__(TrustedWorkspaceBuilder)
    builder.strategies = SimpleNamespace(
        get_opportunity=lambda ref: SimpleNamespace(id=ref, strategy_artifact_id=44),
        get_strategy_artifact=lambda ref: SimpleNamespace(id=ref, account_id=8),
    )
    selection = StructuredContext(references=[TrustedContextRef(
        ref=ObjectRef(type=ResolvedObjectType.CONTENT_OPPORTUNITY, id=9), account_ref=7
    )])
    assert builder.build(selection).opportunity_strategy_ref is None


def test_published_note_exact_identity_is_passed_to_review_workflow():
    invoker = FakeInvoker()
    deps = _deps(workspace=TrustedWorkspaceSnapshot(published_note_ref=123), invoker=invoker)
    run_post_publish_review(_ctx(deps), "复盘发布表现")
    assert invoker.calls[0][0].input["published_note_ref"] == 123
    assert "draft_version_id" not in invoker.calls[0][0].input


def test_tool_failed_overrides_model_success_text():
    ledger = TurnExecutionLedger(outcomes=[WorkflowToolOutcome(
        tool_name="run_research", workflow_name="RESEARCH_V1", status=WorkflowStatus.FAILED,
        user_message="研究失败", error_code="PROVIDER_NOT_CONFIGURED",
    )])
    result = ConversationResponseMapper().map(ConversationResponse(message="已经完成"), ledger)
    assert result.status == WorkflowStatus.FAILED
    assert result.message == "研究失败"
    assert result.error == {"code": "PROVIDER_NOT_CONFIGURED"}


def test_tool_waiting_overrides_model_response():
    ledger = TurnExecutionLedger(outcomes=[WorkflowToolOutcome(
        tool_name="run_content_refinement", workflow_name="CONTENT_REFINEMENT_V1",
        status=WorkflowStatus.WAITING_USER, user_message="请先选择草稿", required_fields=["draft"],
    )])
    result = ConversationResponseMapper().map(ConversationResponse(message="已修改"), ledger)
    assert result.action == RuntimeAction.CLARIFY
    assert result.status == WorkflowStatus.WAITING_USER


def test_direct_chat_stays_success_and_unsupported_has_frozen_warning():
    mapper = ConversationResponseMapper()
    direct = mapper.map(ConversationResponse(message="你好"), TurnExecutionLedger())
    unsupported = mapper.map(ConversationResponse(message="不支持自动发布", response_kind=ConversationResponseKind.UNSUPPORTED), TurnExecutionLedger())
    assert (direct.intent, direct.action, direct.status) == (Intent.GENERAL_CHAT, RuntimeAction.RESPOND, WorkflowStatus.SUCCESS)
    assert unsupported.intent == Intent.UNKNOWN
    assert unsupported.warnings == ["UNSUPPORTED_CAPABILITY"]


def test_capability_snapshot_only_claims_frozen_capabilities():
    assert len(CAPABILITIES.workflows) == 5
    assert all("自动发布" not in item and "自动评论" not in item for item in CAPABILITIES.workflows)
    assert any("自动发布" in item for item in CAPABILITIES.unsupported)


@pytest.mark.parametrize(
    ("tool", "deps", "argument", "workflow", "identity_key", "identity_value"),
    [
        (run_research, _deps(materials=AgentTurnMaterials(note_urls=["https://www.xiaohongshu.com/explore/n1"])), "研究这篇", "RESEARCH_V1", "note_urls", ["https://www.xiaohongshu.com/explore/n1"]),
        (run_content_strategy, _deps(workspace=TrustedWorkspaceSnapshot(research_ref=11)), "制定策略", "CONTENT_STRATEGY_V1", "research_artifact_ref", {"type": "RESEARCH", "id": 11}),
        (run_content_creation, _deps(workspace=TrustedWorkspaceSnapshot(opportunity_ref=12, opportunity_strategy_ref=13)), "写一篇", "CONTENT_CREATION_V1", "opportunity_ref", 12),
        (run_content_refinement, _deps(workspace=TrustedWorkspaceSnapshot(draft_ref=14)), "开头更直接", "CONTENT_REFINEMENT_V1", "draft_ref", 14),
        (run_post_publish_review, _deps(workspace=TrustedWorkspaceSnapshot(published_note_ref=15)), "复盘", "POST_PUBLISH_REVIEW_V1", "published_note_ref", 15),
    ],
)
def test_workflow_adapters_invoke_existing_runtime_with_trusted_identity(tool, deps, argument, workflow, identity_key, identity_value):
    outcome = tool(_ctx(deps), argument)
    request = deps.workflow_invoker.calls[0][0]
    assert request.workflow_name.value == workflow
    assert request.input["account_ref"] == 7
    assert request.input[identity_key] == identity_value
    assert outcome.run_ref == "run-7"
    assert outcome.status == WorkflowStatus.SUCCESS


def _agent_deps(*, workspace=None, materials=None, invoker=None, gate=None):
    return _deps(workspace=workspace, materials=materials, invoker=invoker, gate=gate)


def _gate(mode):
    return ExecutionGateResult(
        mode=mode,
        confidence=1,
        reason_code=(
            ExecutionGateReason.EXPLICIT_BUSINESS_ACTION
            if mode == ExecutionMode.BUSINESS_ACTION
            else ExecutionGateReason.CASUAL_CONVERSATION
        ),
    )


@pytest.mark.parametrize(
    "case_text",
    [
        "你好",
        "你能做什么",
        "你是怎么知道的",
        "现在起你叫张三",
        "你现在叫张三",
        "你有记忆吗",
        "你记得我刚才让你叫什么吗",
        "什么是内容策略",
        "复盘是什么意思",
        "你能修改草稿吗",
        "为什么你不能自动发布",
        "我跟你普通聊聊天",
    ],
)
def test_chat_cases_expose_zero_workflow_tools_and_create_no_run(case_text):
    model = TestModel(
        call_tools=[],
        custom_output_args={"message": "正常对话回复", "response_kind": "RESPOND", "required_fields": []},
    )
    deps = _agent_deps(gate=_gate(ExecutionMode.CONVERSATION))

    output = build_conversation_agent(model).run_sync(case_text, deps=deps).output
    result = ConversationResponseMapper().map(output, deps.turn_execution_ledger)

    assert model.last_model_request_parameters.function_tools == []
    assert deps.turn_execution_ledger.outcomes == []
    assert result.run_ref is None
    assert result.status == WorkflowStatus.SUCCESS


@pytest.mark.parametrize(
    "case_text,workspace,materials,tool_name,visible_tools",
    [
        ("根据刚才研究制定内容策略", TrustedWorkspaceSnapshot(research_ref=11), AgentTurnMaterials(), "run_content_strategy", {"run_research", "run_content_strategy"}),
        ("把这个草稿改短一点", TrustedWorkspaceSnapshot(draft_ref=14), AgentTurnMaterials(), "run_content_refinement", {"run_research", "run_content_refinement"}),
        ("复盘一下这篇", TrustedWorkspaceSnapshot(published_note_ref=15), AgentTurnMaterials(), "run_post_publish_review", {"run_research", "run_post_publish_review"}),
        (
            "分析这篇为什么容易火",
            TrustedWorkspaceSnapshot(),
            AgentTurnMaterials(note_urls=["https://www.xiaohongshu.com/explore/n1?xsec_token=keep"]),
            "run_research",
            {"run_research"},
        ),
    ],
)
def test_minimal_pair_business_side_opens_tools_and_selects_expected_workflow(
    case_text, workspace, materials, tool_name, visible_tools
):
    model = TestModel(
        call_tools=[tool_name],
        custom_output_args={"message": "完成", "response_kind": "RESPOND", "required_fields": []},
    )
    deps = _agent_deps(
        workspace=workspace,
        materials=materials,
        gate=_gate(ExecutionMode.BUSINESS_ACTION),
    )

    build_conversation_agent(model).run_sync(case_text, deps=deps)

    visible = {tool.name for tool in model.last_model_request_parameters.function_tools}
    assert visible == visible_tools
    assert deps.turn_execution_ledger.last.tool_name == tool_name


@pytest.mark.parametrize(
    ("case_text", "message", "kind"),
    [
        ("你能做什么", "我支持研究、策略、创作、草稿修改和发布后复盘五类能力。", "RESPOND"),
        ("你有哪些 skill", "我有研究、策略、创作、修改和复盘五类业务技能。", "RESPOND"),
        ("你有哪些工具", "我可以调用研究、策略、创作、修改和复盘工作流。", "RESPOND"),
        ("帮我自动发布", "当前不支持自动发布，可以帮你准备待发布内容，最终需人工发布。", "UNSUPPORTED"),
        ("帮我自动评论", "当前不支持自动评论，可以帮你分析内容和评论需求。", "UNSUPPORTED"),
        ("这篇写得太差", "你希望重点改标题、开头、结构、表达，还是整体重写？", "NEED_USER_INPUT"),
    ],
)
def test_agent_behavior_direct_cases_with_deterministic_model(case_text, message, kind):
    model = TestModel(call_tools=[], custom_output_args={"message": message, "response_kind": kind, "required_fields": []})
    agent = build_conversation_agent(model)
    deps = _agent_deps(workspace=TrustedWorkspaceSnapshot(draft_ref=2625))
    output = agent.run_sync(case_text, deps=deps).output
    result = ConversationResponseMapper().map(output, deps.turn_execution_ledger)
    assert result.message == message
    assert not deps.turn_execution_ledger.outcomes
    if kind == "UNSUPPORTED":
        assert result.warnings == ["UNSUPPORTED_CAPABILITY"]
    if case_text == "这篇写得太差":
        assert result.status == WorkflowStatus.WAITING_USER


def test_d02_external_note_selects_research_with_deterministic_model():
    note = "https://www.xiaohongshu.com/explore/n1?xsec_token=keep"
    invoker = FakeInvoker(status=WorkflowStatus.FAILED, error={"code": "PROVIDER_NOT_CONFIGURED"})
    deps = _agent_deps(materials=AgentTurnMaterials(note_urls=[note]), invoker=invoker)
    model = TestModel(call_tools=["run_research"], custom_output_args={"message": "完成", "response_kind": "RESPOND", "required_fields": []})
    output = build_conversation_agent(model).run_sync("分析这篇", deps=deps).output
    result = ConversationResponseMapper().map(output, deps.turn_execution_ledger)
    assert deps.turn_execution_ledger.last.tool_name == "run_research"
    assert invoker.calls[0][0].input["note_urls"] == [note]
    assert result.intent == Intent.RESEARCH
    assert result.status == WorkflowStatus.FAILED


def test_k01_history_can_constrain_next_title_without_long_term_memory():
    model = TestModel(call_tools=[], custom_output_args={"message": "这个标题更直接：新手也能照做的三步法", "response_kind": "RESPOND", "required_fields": []})
    history = [
        ModelRequest(parts=[UserPromptPart(content="我不喜欢标题里用逆袭")]),
        ModelResponse(parts=[TextPart(content="明白，我会避开这个词。")]),
    ]
    output = build_conversation_agent(model).run_sync("再给我一个标题", message_history=history, deps=_agent_deps()).output
    assert "逆袭" not in output.message


def test_l02_clarification_then_profile_url_selects_research():
    first_deps = _agent_deps()
    waiting_model = TestModel(call_tools=["run_research"], custom_output_args={"message": "完成", "response_kind": "RESPOND", "required_fields": []})
    first_output = build_conversation_agent(waiting_model).run_sync("帮我分析一个同行账号", deps=first_deps).output
    first = ConversationResponseMapper().map(first_output, first_deps.turn_execution_ledger)
    assert first.status == WorkflowStatus.WAITING_USER
    assert first.pending_interaction.required_fields == ["research_material"]

    profile = "https://www.xiaohongshu.com/user/profile/u1?xsec_token=keep"
    second_deps = _agent_deps(materials=AgentTurnMaterials(profile_urls=[profile]))
    second_model = TestModel(call_tools=["run_research"], custom_output_args={"message": "完成", "response_kind": "RESPOND", "required_fields": []})
    second_output = build_conversation_agent(second_model).run_sync(
        profile,
        deps=second_deps,
    ).output
    second = ConversationResponseMapper().map(second_output, second_deps.turn_execution_ledger)
    assert second.intent == Intent.RESEARCH
    assert second_deps.workflow_invoker.calls[0][0].input["profile_urls"] == [profile]


def test_verified_pending_research_continuation_resumes_same_run_without_starting_new_run():
    profile = "https://www.xiaohongshu.com/user/profile/u1?xsec_token=keep"
    materials = AgentTurnMaterials(profile_urls=[profile])
    invoker = FakeInvoker()
    deps = _deps(materials=materials, invoker=invoker)
    pending = PendingFact(
        workflow_type=WorkflowId.RESEARCH_V1,
        required_fields=("research_material",),
        resumable=True,
        requirements_satisfied=True,
    )
    deps.decision_context = CanonicalTurnContextBuilder().build(
        current_materials=(NormalizedCurrentMaterial(
            material_type=CurrentMaterialType.EXTERNAL_XHS_PROFILE,
            source_url=profile,
            source=CurrentMaterialSource.EXPLICIT_MATERIAL,
        ),),
        workspace=deps.trusted_workspace,
        recent=deps.recent_context,
        pending=pending,
    )
    deps.active_pending_run_ref = "run-pending"
    deps.active_pending_checkpoint_version = 3

    outcome = run_research(_ctx(deps), "继续分析")

    assert invoker.calls == []
    assert len(invoker.resume_calls) == 1
    assert invoker.resume_calls[0][0].run_ref == "run-pending"
    assert invoker.resume_calls[0][0].expected_checkpoint_version == 3
    assert outcome.run_ref == "run-pending"
