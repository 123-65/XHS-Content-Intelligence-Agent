import json

from app.agent.product_entry.confirmation import build_confirmation_card
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.schemas import (
    Action,
    AgentChatResponse,
    AgentInput,
    AgentResponseStatus,
    AllowedEffect,
    ConfirmationRequirement,
    Intent,
    ParamValidationResult,
    Plan,
    PlanStep,
    PlanValidationResult,
    RiskFlag,
    RouterResult,
    ValidationIssue,
    ValidationSeverity,
)
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.agent.product_entry.trace import (
    AgentEntryTraceRecorder,
    AgentEntryTraceStage,
    mask_sensitive_text,
    summarize_payload,
    to_agent_trace_payload,
)
from app.agent.product_entry.validators import validate_plan_params, validate_plan_result


class FakeLLMClient:
    """测试用 LLMClient，不调用真实模型。"""

    def __init__(self, output: str):
        """保存预置输出。"""
        self.output = output

    def generate_text(self, *args, **kwargs):
        """返回预置输出。"""
        return self.output


def _router_json(**overrides):
    """构造 RouterResult JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "confidence": 0.9,
        "input_type": "TEXT",
        "extracted_params": {"account_id": 1, "topic": "职场成长"},
        "missing_params": [],
        "risk_flags": [],
        "requires_clarification": False,
        "requires_confirmation": False,
        "can_execute": True,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _plan_json(**overrides):
    """构造 Plan JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "steps": [
            {
                "step_no": 1,
                "action": "GENERATE_CONTENT_OPPORTUNITY",
                "description": "生成内容机会。",
                "input_params": {"account_id": 1, "topic": "职场成长"},
                "expected_output": "内容机会",
                "allowed_effect": "LOCAL_GENERATION",
            }
        ],
        "missing_params": [],
        "risk_flags": [],
        "confirmation_requirement": "NONE",
        "can_execute": True,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _stages(recorder: AgentEntryTraceRecorder):
    """读取 recorder 已记录阶段。"""
    return [event.stage for event in recorder.events]


def test_trace_recorder_records_input_received():
    """测试 AgentEntryTraceRecorder 可以记录 INPUT_RECEIVED。"""
    recorder = AgentEntryTraceRecorder(session_id="s1")

    recorder.record_input(AgentInput(conversation_id="s1", account_id=1, user_input="hello"))

    assert recorder.events[0].stage == AgentEntryTraceStage.INPUT_RECEIVED
    assert recorder.build_trace().account_id == 1


def test_record_router_result_records_intent_missing_params_and_risk_flags():
    """测试 record_router_result 可以记录 intent / missing_params / risk_flags。"""
    recorder = AgentEntryTraceRecorder()
    result = RouterResult(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        missing_params=["target"],
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
    )

    recorder.record_router_result(result)

    event = recorder.events[0]
    assert event.intent == Intent.REFINE_OR_REJECT_RESULT
    assert event.missing_params == ["target"]
    assert RiskFlag.TARGET_AMBIGUOUS in event.risk_flags


def test_record_plan_records_steps_count_and_confirmation_requirement():
    """测试 record_plan 可以记录 steps 数量和确认要求。"""
    recorder = AgentEntryTraceRecorder()
    plan = Plan(
        intent=Intent.GENERATE_CONTENT_OPPORTUNITY,
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        steps=[PlanStep(step_no=1, action=Action.CREATE_CANDIDATE_MEMORY, description="暂存记忆", allowed_effect=AllowedEffect.LOCAL_WRITE)],
    )

    recorder.record_plan(plan)

    event = recorder.events[0]
    assert event.payload["steps_count"] == 1
    assert event.confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED


def test_record_param_validation_records_missing_param_issues():
    """测试 record_param_validation 可以记录缺参问题。"""
    recorder = AgentEntryTraceRecorder()
    validation = ParamValidationResult(
        valid=False,
        missing_params=["step_1.account_id"],
        issues=[
            ValidationIssue(
                field="step_1.account_id",
                message="缺少 account_id",
                risk_flag=RiskFlag.MISSING_REQUIRED_PARAM,
                severity=ValidationSeverity.BLOCKER,
            )
        ],
    )

    recorder.record_param_validation(validation)

    event = recorder.events[0]
    assert event.stage == AgentEntryTraceStage.PARAM_VALIDATED
    assert event.missing_params == ["step_1.account_id"]


def test_record_plan_validation_records_blocked_reason():
    """测试 record_plan_validation 可以记录阻断原因。"""
    recorder = AgentEntryTraceRecorder()
    validation = PlanValidationResult(
        valid=False,
        confirmation_requirement=ConfirmationRequirement.BLOCKED,
        risk_flags=[RiskFlag.EXTERNAL_WRITE],
        blocked_reason="当前阶段不支持外部写入。",
    )

    recorder.record_plan_validation(validation)

    event = recorder.events[0]
    assert event.confirmation_requirement == ConfirmationRequirement.BLOCKED
    assert event.warning == "当前阶段不支持外部写入。"


def test_record_confirmation_card_records_clarification_card():
    """测试 record_confirmation_card 可以记录澄清卡片。"""
    recorder = AgentEntryTraceRecorder()
    card = build_confirmation_card(Plan(confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED, missing_params=["account_id"]))

    recorder.record_confirmation_card(card)

    assert recorder.events[0].payload["title"] == "需要补充信息"


def test_record_confirmation_card_records_confirmation_card():
    """测试 record_confirmation_card 可以记录确认卡片。"""
    recorder = AgentEntryTraceRecorder()
    card = build_confirmation_card(
        Plan(
            confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
            steps=[PlanStep(step_no=1, action=Action.CREATE_CANDIDATE_MEMORY, description="记忆", allowed_effect=AllowedEffect.LOCAL_WRITE)],
        )
    )

    recorder.record_confirmation_card(card)

    assert recorder.events[0].confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED


def test_record_confirmation_card_records_blocked_card():
    """测试 record_confirmation_card 可以记录阻断卡片。"""
    recorder = AgentEntryTraceRecorder()
    card = build_confirmation_card(
        Plan(
            confirmation_requirement=ConfirmationRequirement.BLOCKED,
            risk_flags=[RiskFlag.EXTERNAL_WRITE],
            blocked_reason="当前阶段不支持自动发布。",
        )
    )

    recorder.record_confirmation_card(card)

    assert recorder.events[0].payload["title"] == "当前无法执行"


def test_record_response_updates_final_status_and_can_execute():
    """测试 record_response 可以更新 final_status / final_can_execute。"""
    recorder = AgentEntryTraceRecorder()
    response = AgentChatResponse(status=AgentResponseStatus.READY_TO_EXECUTE, can_execute=True, message="ok")

    recorder.record_response(response)
    trace = recorder.build_trace()

    assert trace.final_status == AgentResponseStatus.READY_TO_EXECUTE
    assert trace.final_can_execute is True


def test_mask_sensitive_text_masks_openai_style_key():
    """测试 mask_sensitive_text 能脱敏 sk- 开头 key。"""
    masked = mask_sensitive_text("key=sk-1234567890abcdef")

    assert masked == "key=sk-***"


def test_mask_sensitive_text_masks_bearer_token():
    """测试 mask_sensitive_text 能脱敏 bearer token。"""
    masked = mask_sensitive_text("Authorization: Bearer abc.def-123")

    assert masked == "Authorization: Bearer ***"


def test_mask_sensitive_text_masks_xhs_query_token():
    masked = mask_sensitive_text(
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=private-value&xsec_source=pc_feed"
    )

    assert masked == "https://www.xiaohongshu.com/explore/note-1?xsec_token=***&xsec_source=pc_feed"


def test_summarize_payload_limits_long_text():
    """测试 summarize_payload 能限制超长文本。"""
    payload = summarize_payload({"text": "a" * 100}, max_chars=10)

    assert payload["text"] == "aaaaaaaaaa...[truncated]"


def test_router_success_records_prompt_parsed_and_validated_events():
    """测试 Router 成功时能记录 ROUTER_PROMPT_BUILT / ROUTER_RESULT_PARSED / ROUTER_VALIDATED。"""
    recorder = AgentEntryTraceRecorder()
    router = LLMUserInputRouter(FakeLLMClient(_router_json()))

    router.route(AgentInput(account_id=1, user_input="帮我找选题"), recorder)

    stages = _stages(recorder)
    assert AgentEntryTraceStage.ROUTER_PROMPT_BUILT in stages
    assert AgentEntryTraceStage.ROUTER_RESULT_PARSED in stages
    assert AgentEntryTraceStage.ROUTER_VALIDATED in stages


def test_router_invalid_json_records_failed_event():
    """测试 Router 非法 JSON 时能记录 FAILED。"""
    recorder = AgentEntryTraceRecorder()
    router = LLMUserInputRouter(FakeLLMClient("not json"))

    router.route(AgentInput(user_input="帮我找选题"), recorder)

    assert AgentEntryTraceStage.FAILED in _stages(recorder)


def test_planner_success_records_prompt_parsed_registry_and_validated_events():
    """测试 Planner 成功时能记录 Planner 关键节点。"""
    recorder = AgentEntryTraceRecorder()
    planner = LLMTaskPlanner(FakeLLMClient(_plan_json()))

    planner.plan(
        AgentInput(account_id=1, user_input="帮我找选题"),
        RouterResult(intent=Intent.GENERATE_CONTENT_OPPORTUNITY, confidence=0.9, extracted_params={"account_id": 1}, can_execute=True),
        recorder,
    )

    stages = _stages(recorder)
    assert AgentEntryTraceStage.PLANNER_PROMPT_BUILT in stages
    assert AgentEntryTraceStage.PLAN_PARSED in stages
    assert AgentEntryTraceStage.PLAN_REGISTRY_APPLIED in stages
    assert AgentEntryTraceStage.PLAN_VALIDATED in stages


def test_planner_failure_records_failed_event():
    """测试 Planner 失败时能记录 FAILED。"""
    recorder = AgentEntryTraceRecorder()
    planner = LLMTaskPlanner(FakeLLMClient("not json"))

    planner.plan(
        AgentInput(account_id=1, user_input="帮我找选题"),
        RouterResult(intent=Intent.GENERATE_CONTENT_OPPORTUNITY, confidence=0.9, extracted_params={"account_id": 1}, can_execute=True),
        recorder,
    )

    assert AgentEntryTraceStage.FAILED in _stages(recorder)


def test_full_entry_flow_builds_trace_with_same_trace_id():
    """测试完整入口链路可以生成一个 trace_id 一致的 AgentEntryTrace。"""
    recorder = AgentEntryTraceRecorder(session_id="s1")
    agent_input = AgentInput(conversation_id="s1", account_id=1, user_input="帮我找选题")
    router = LLMUserInputRouter(FakeLLMClient(_router_json()))
    planner = LLMTaskPlanner(FakeLLMClient(_plan_json()))

    recorder.record_input(agent_input)
    router_result = router.route(agent_input, recorder)
    plan = planner.plan(agent_input, router_result, recorder)
    param_validation = validate_plan_params(plan)
    recorder.record_param_validation(param_validation)
    validated_plan = validate_plan_result(plan)
    card = build_confirmation_card(validated_plan)
    recorder.record_confirmation_card(card)
    recorder.record_response(
        AgentChatResponse(
            session_id="s1",
            router_result=router_result,
            plan=validated_plan,
            status=AgentResponseStatus.READY_TO_EXECUTE if validated_plan.can_execute else AgentResponseStatus.NEED_CLARIFICATION,
            can_execute=validated_plan.can_execute,
            requires_confirmation=card is not None,
            confirmation_card=card,
            message="done",
            trace_id=recorder.trace_id,
        )
    )
    trace = recorder.build_trace()

    assert trace.trace_id
    assert all(event.trace_id == trace.trace_id for event in trace.events)
    assert trace.session_id == "s1"


def test_trace_payload_masks_secret_and_api_key():
    """测试 Trace payload 不包含明文 secret / api_key。"""
    recorder = AgentEntryTraceRecorder()

    recorder.record_event(
        AgentEntryTraceStage.INPUT_RECEIVED,
        payload={"api_key": "sk-1234567890abcdef", "nested": {"secret": "plain", "text": "Bearer abc.def"}},
    )

    dumped = json.dumps(recorder.build_trace().model_dump(mode="json"), ensure_ascii=False)
    assert "sk-1234567890abcdef" not in dumped
    assert "plain" not in dumped
    assert "Bearer abc.def" not in dumped


def test_trace_can_convert_to_agent_trace_payload():
    """测试入口层 Trace 可以转换为现有 Agent Trace 轻量 payload。"""
    recorder = AgentEntryTraceRecorder()
    recorder.record_input(AgentInput(account_id=1, user_input="hello"))

    payload = to_agent_trace_payload(recorder.build_trace())

    assert payload["agent_type"] == "PRODUCT_ENTRY_AGENT"
    assert payload["workflow_name"] == "router_planner_entry"
    assert payload["events"][0]["stage"] == AgentEntryTraceStage.INPUT_RECEIVED.value
