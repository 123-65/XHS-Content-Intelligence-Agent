import json

from app.agent.product_entry.execution import ExecutionMode
from app.agent.product_entry.executor import ActionHandlerRegistry, ExecutionOrchestrator
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.pipeline import AgentEntryPreviewPipeline, build_agent_input_from_chat_request
from app.agent.product_entry.schemas import (
    Action,
    AgentChatRequest,
    AgentChatResponse,
    AgentResponseStatus,
    AllowedEffect,
    ConfirmationRequirement,
    InputType,
    Intent,
    RiskFlag,
    TargetType,
)
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.agent.product_entry.trace import AgentEntryTraceStage


class FakeLLMClient:
    """测试用 FakeLLMClient，不调用真实模型。"""

    def __init__(self, output: str):
        """保存预置输出。"""
        self.output = output
        self.calls = []

    def generate_text(self, prompt: str, system_prompt: str | None = None, **kwargs):
        """记录调用并返回预置 JSON 文本。"""
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt, "kwargs": kwargs})
        return self.output


def _router_payload(**overrides) -> str:
    """构造 RouterResult JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "confidence": 0.9,
        "input_type": "TEXT",
        "target_type": "UNKNOWN",
        "feedback_action": "UNKNOWN",
        "feedback_polarity": "UNKNOWN",
        "extracted_params": {"topic": "27 届双非本科做 Agent 求职"},
        "missing_params": [],
        "risk_flags": [],
        "requires_clarification": False,
        "requires_confirmation": False,
        "can_execute": True,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _plan_payload(steps=None, **overrides) -> str:
    """构造 Plan JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "steps": steps
        if steps is not None
        else [
            {
                "step_no": 1,
                "action": "GENERATE_CONTENT_OPPORTUNITY",
                "description": "把用户想法整理成内容机会。",
                "input_params": {"account_id": 1, "topic": "27 届双非本科做 Agent 求职"},
                "expected_output": "内容机会预览",
                "allowed_effect": "LOCAL_GENERATION",
                "can_execute": True,
            }
        ],
        "missing_params": [],
        "risk_flags": [],
        "confirmation_requirement": "NONE",
        "can_execute": True,
        "summary_for_user": "已规划入口链路预览。",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _pipeline(router_output: str, planner_output: str, orchestrator: ExecutionOrchestrator | None = None):
    """构造入口预览 Pipeline。"""
    router_client = FakeLLMClient(router_output)
    planner_client = FakeLLMClient(planner_output)
    pipeline = AgentEntryPreviewPipeline(
        LLMUserInputRouter(router_client),
        LLMTaskPlanner(planner_client),
        orchestrator=orchestrator,
    )
    return pipeline, router_client, planner_client


def _preview(router_output: str, planner_output: str, request: AgentChatRequest | None = None) -> AgentChatResponse:
    """执行一次默认预览。"""
    pipeline, _, _ = _pipeline(router_output, planner_output)
    return pipeline.preview(request or AgentChatRequest(session_id="s1", account_id=1, text="帮我找一个选题"))


def _trace_stages(response: AgentChatResponse) -> list[str]:
    """读取 response metadata 中的 entry_trace stage。"""
    return [event["stage"] for event in response.metadata["entry_trace"]["events"]]


def test_preview_returns_agent_chat_response():
    """测试 preview 能返回 AgentChatResponse。"""
    response = _preview(_router_payload(), _plan_payload())

    assert isinstance(response, AgentChatResponse)


def test_preview_generates_trace_id():
    """测试 preview 会生成 trace_id。"""
    response = _preview(_router_payload(), _plan_payload())

    assert response.trace_id


def test_preview_metadata_contains_entry_trace():
    """测试 preview metadata 中包含 entry_trace。"""
    response = _preview(_router_payload(), _plan_payload())

    assert response.metadata["entry_trace"]["trace_id"] == response.trace_id


def test_ambiguous_feedback_without_target_returns_need_clarification():
    """测试“这个不行”且无 target 返回 NEED_CLARIFICATION。"""
    response = _preview(
        _router_payload(
            intent="REFINE_OR_REJECT_RESULT",
            target_type="UNKNOWN",
            feedback_action="REJECT",
            feedback_polarity="NEGATIVE",
            can_execute=True,
        ),
        _plan_payload(),
        AgentChatRequest(session_id="s1", text="这个不行", input_type=InputType.TEXT),
    )

    assert response.status == AgentResponseStatus.NEED_CLARIFICATION
    assert response.can_execute is False
    assert response.confirmation_card.title == "需要补充信息"


def test_title_ai_with_current_target_can_plan_refine():
    """测试“标题太 AI”且有 current_target 返回可规划 refine。"""
    steps = [
        {
            "step_no": 1,
            "action": "REFINE_DRAFT",
            "description": "把当前草稿标题改得更自然。",
            "input_params": {"account_id": 1, "draft_id": 123, "feedback": "标题太 AI，换自然一点", "scope": "title"},
            "expected_output": "更自然的标题候选",
            "allowed_effect": "LOCAL_GENERATION",
            "can_execute": True,
        }
    ]
    response = _preview(
        _router_payload(
            intent="REFINE_OR_REJECT_RESULT",
            target_type="DRAFT",
            target_id=123,
            feedback_action="REFINE",
            feedback_polarity="NEGATIVE",
            extracted_params={"scope": "title"},
        ),
        _plan_payload(intent="REFINE_OR_REJECT_RESULT", steps=steps),
        AgentChatRequest(
            session_id="s1",
            account_id=1,
            text="这个标题太 AI 了，换自然一点",
            current_target_type=TargetType.DRAFT,
            current_target_id=123,
        ),
    )

    assert response.router_result.target_id == 123
    assert response.plan.steps[0].action == Action.REFINE_DRAFT
    assert response.plan.steps[0].input_params["draft_id"] == 123


def test_auto_publish_xhs_returns_blocked():
    """测试自动发布小红书返回 BLOCKED。"""
    steps = [
        {
            "step_no": 1,
            "action": "NOOP",
            "description": "尝试自动发布到小红书。",
            "input_params": {"account_id": 1},
            "expected_output": "外部发布",
            "allowed_effect": "EXTERNAL_WRITE",
            "risk_flags": ["EXTERNAL_WRITE", "CAPABILITY_BOUNDARY_EXCEEDED"],
            "can_execute": True,
        }
    ]
    response = _preview(
        _router_payload(intent="GENERATE_DRAFT", extracted_params={"account_id": 1}, risk_flags=["EXTERNAL_WRITE"]),
        _plan_payload(intent="GENERATE_DRAFT", steps=steps),
        AgentChatRequest(session_id="s1", account_id=1, text="直接帮我发布到小红书"),
    )

    assert response.status == AgentResponseStatus.BLOCKED
    assert response.can_execute is False
    assert response.confirmation_card.title == "当前无法执行"
    assert RiskFlag.EXTERNAL_WRITE in response.plan_validation.risk_flags
    assert RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED in response.plan_validation.risk_flags


def test_missing_params_returns_clarification_card():
    """测试参数缺失时返回澄清卡片。"""
    steps = [
        {
            "step_no": 1,
            "action": "GENERATE_CONTENT_OPPORTUNITY",
            "description": "生成内容机会。",
            "input_params": {"topic": "27 届双非本科做 Agent 求职"},
            "expected_output": "内容机会",
            "allowed_effect": "LOCAL_GENERATION",
            "can_execute": True,
        }
    ]
    response = _preview(
        _router_payload(extracted_params={"topic": "27 届双非本科做 Agent 求职"}),
        _plan_payload(steps=steps),
        AgentChatRequest(session_id="s1", text="我想写一篇 27 届双非本科做 Agent 求职的帖子"),
    )

    assert response.status == AgentResponseStatus.NEED_CLARIFICATION
    assert "step_1.account_id" in response.param_validation.missing_params
    assert response.confirmation_card.title == "需要补充信息"


def test_confirmation_required_returns_confirmation_card():
    """测试需要确认时返回确认卡片。"""
    steps = [
        {
            "step_no": 1,
            "action": "CREATE_CANDIDATE_MEMORY",
            "description": "把用户偏好暂存为候选记忆。",
            "input_params": {"account_id": 1, "memory_content": "用户不喜欢 AI 味标题", "source": "user_feedback"},
            "allowed_effect": "LOCAL_WRITE",
            "requires_confirmation": True,
        }
    ]
    response = _preview(
        _router_payload(
            intent="REFINE_OR_REJECT_RESULT",
            target_type="DRAFT",
            target_id=123,
            extracted_params={"account_id": 1},
        ),
        _plan_payload(intent="REFINE_OR_REJECT_RESULT", steps=steps),
    )

    assert response.status == AgentResponseStatus.WAITING_CONFIRMATION
    assert response.requires_confirmation is True
    assert response.confirmation_card.title == "请确认执行计划"


def test_preview_always_uses_dry_run_not_real():
    """测试 preview 永远使用 DRY_RUN，不使用 REAL。"""
    response = _preview(_router_payload(), _plan_payload())

    assert response.metadata["execution"]["mode"] == ExecutionMode.DRY_RUN.value


def test_preview_does_not_call_business_handler():
    """测试 preview 不调用业务 handler。"""
    called = {"value": False}
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: called.update(value=True) or {"ok": True})
    orchestrator = ExecutionOrchestrator(registry)
    pipeline, _, _ = _pipeline(_router_payload(), _plan_payload(), orchestrator=orchestrator)

    response = pipeline.preview(AgentChatRequest(session_id="s1", account_id=1, text="帮我找一个选题"))

    assert response.status == AgentResponseStatus.READY_TO_EXECUTE
    assert called["value"] is False


def test_entry_trace_contains_router_planner_validator_and_orchestrator_events():
    """测试 Router / Planner / Validator / Orchestrator Trace 都进入 entry_trace。"""
    response = _preview(_router_payload(), _plan_payload())
    stages = _trace_stages(response)

    assert AgentEntryTraceStage.ROUTER_VALIDATED.value in stages
    assert AgentEntryTraceStage.PLAN_VALIDATED.value in stages
    assert AgentEntryTraceStage.PARAM_VALIDATED.value in stages
    assert AgentEntryTraceStage.EXECUTION_STARTED.value in stages
    assert AgentEntryTraceStage.EXECUTION_FINISHED.value in stages


def test_agent_chat_request_does_not_backfill_account_id():
    """测试 AgentChatRequest 不会被补造 account_id。"""
    agent_input = build_agent_input_from_chat_request(AgentChatRequest(session_id="s1", text="帮我写帖子"))

    assert agent_input.account_id is None


def test_current_target_id_passes_to_router_result_and_plan():
    """测试 current_target_id 能传递到 RouterResult / Plan。"""
    response = _preview(
        _router_payload(intent="REFINE_OR_REJECT_RESULT", target_type="DRAFT", target_id=123, extracted_params={"scope": "title"}),
        _plan_payload(
            intent="REFINE_OR_REJECT_RESULT",
            steps=[
                {
                    "step_no": 1,
                    "action": "REFINE_DRAFT",
                    "description": "修改当前草稿。",
                    "input_params": {"account_id": 1, "draft_id": 123, "feedback": "标题太 AI"},
                    "allowed_effect": "LOCAL_GENERATION",
                }
            ],
        ),
        AgentChatRequest(session_id="s1", account_id=1, text="标题太 AI", current_target_type=TargetType.DRAFT, current_target_id="123"),
    )

    assert response.router_result.target_id == 123
    assert response.plan.steps[0].input_params["draft_id"] == 123


def test_invalid_router_output_safely_returns_unknown_need_clarification():
    """测试非法 Router 输出能安全返回 UNKNOWN / NEED_CLARIFICATION。"""
    response = _preview("not json", _plan_payload())

    assert response.router_result.intent == Intent.UNKNOWN
    assert response.status == AgentResponseStatus.NEED_CLARIFICATION
    assert response.can_execute is False


def test_invalid_planner_output_safely_returns_safe_plan():
    """测试非法 Planner 输出能安全返回安全 Plan。"""
    response = _preview(_router_payload(), "not json")

    assert response.plan.intent == Intent.GENERATE_CONTENT_OPPORTUNITY
    assert response.plan.can_execute is False
    assert response.status == AgentResponseStatus.NEED_CLARIFICATION


def test_dry_run_preview_success_message_is_preview_only():
    """测试参数齐全且无确认时返回 dry-run 可执行预览。"""
    response = _preview(_router_payload(), _plan_payload())

    assert response.status == AgentResponseStatus.READY_TO_EXECUTE
    assert response.can_execute is True
    assert response.message == "计划已通过校验，本阶段仅预演，不执行业务。"
