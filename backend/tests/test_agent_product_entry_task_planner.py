import json

from app.agent.product_entry.prompts import build_task_planner_system_prompt
from app.agent.product_entry.schemas import (
    Action,
    AgentInput,
    AllowedEffect,
    ConfirmationRequirement,
    Intent,
    Plan,
    PlanStep,
    RiskFlag,
    RouterResult,
    TargetType,
)
from app.agent.product_entry.task_planner import LLMTaskPlanner, apply_action_registry_constraints
from app.llm.errors import LLMError


class FakeLLMClient:
    """测试用 LLMClient，不调用真实模型或业务服务。"""

    def __init__(self, output: str | None = None, error: Exception | None = None):
        """保存测试输出或异常。"""
        self.output = output
        self.error = error
        self.calls = []

    def generate_text(self, prompt: str, system_prompt: str | None = None, **kwargs):
        """记录调用并返回预置文本。"""
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt, "kwargs": kwargs})
        if self.error:
            raise self.error
        return self.output or "{}"


def _router_result(**overrides):
    """构建已经可以继续规划的 RouterResult。"""
    data = {
        "intent": Intent.GENERATE_CONTENT_OPPORTUNITY,
        "confidence": 0.9,
        "input_type": "TEXT",
        "extracted_params": {"account_id": 1, "topic": "职场成长"},
        "can_execute": True,
    }
    data.update(overrides)
    return RouterResult.model_validate(data)


def _plan_payload(intent="GENERATE_CONTENT_OPPORTUNITY", steps=None, **overrides):
    """构建 LLM 输出的 Plan JSON。"""
    payload = {
        "intent": intent,
        "steps": [
            {
                "step_no": 1,
                "action": "GENERATE_CONTENT_OPPORTUNITY",
                "description": "生成内容机会。",
                "inputs": {"account_id": 1, "topic": "职场成长"},
                "input_params": {"account_id": 1, "topic": "职场成长"},
                "expected_output": "内容机会",
                "allowed_effect": "READ_ONLY",
                "risk_flags": [],
                "requires_confirmation": False,
                "can_execute": True,
            }
        ]
        if steps is None
        else steps,
        "required_params": ["account_id"],
        "missing_params": [],
        "risk_flags": [],
        "confirmation_requirement": "NONE",
        "can_execute": True,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_task_planner_parses_valid_json_to_plan():
    """测试 Planner 能把合法 JSON 解析成 Plan。"""
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload()))

    plan = planner.plan(AgentInput(account_id=1, user_input="帮我找选题"), _router_result())

    assert plan.intent == Intent.GENERATE_CONTENT_OPPORTUNITY
    assert plan.steps[0].action == Action.GENERATE_CONTENT_OPPORTUNITY


def test_task_planner_calls_validate_plan_result():
    """测试 Planner 输出后会经过 validate_plan_result。"""
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload(steps=[], can_execute=True)))

    plan = planner.plan(AgentInput(account_id=1, user_input="帮我找选题"), _router_result())

    assert plan.can_execute is False
    assert RiskFlag.MISSING_REQUIRED_PARAM in plan.risk_flags


def test_task_planner_applies_registry_allowed_effect():
    """测试 Action Registry 会覆盖 LLM 自己填写的 allowed_effect。"""
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload()))

    plan = planner.plan(AgentInput(account_id=1, user_input="帮我找选题"), _router_result())

    assert plan.steps[0].allowed_effect == AllowedEffect.LOCAL_GENERATION
    assert plan.steps[0].required_params == ["account_id"]


def test_task_planner_can_generate_multi_step_draft_plan():
    """测试 GENERATE_DRAFT 可以生成多步骤 Plan。"""
    steps = [
        {
            "step_no": 1,
            "action": "QUERY_ACCOUNT_PROFILE",
            "description": "查询账号画像。",
            "input_params": {"account_id": 1},
            "expected_output": "账号画像",
            "allowed_effect": "READ_ONLY",
        },
        {
            "step_no": 2,
            "action": "QUERY_STRATEGY_MEMORY",
            "description": "查询策略记忆。",
            "input_params": {"account_id": 1},
            "expected_output": "策略记忆",
            "allowed_effect": "READ_ONLY",
        },
        {
            "step_no": 3,
            "action": "GENERATE_DRAFT",
            "description": "生成本地草稿。",
            "input_params": {"account_id": 1, "experiment_id": 9},
            "depends_on": [1, 2],
            "expected_output": "草稿",
            "allowed_effect": "LOCAL_GENERATION",
        },
        {
            "step_no": 4,
            "action": "REVIEW_DRAFT",
            "description": "审核草稿。",
            "input_params": {"draft_id": 20},
            "depends_on": [3],
            "expected_output": "审核结果",
            "allowed_effect": "LOCAL_GENERATION",
        },
    ]
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload(intent="GENERATE_DRAFT", steps=steps)))

    plan = planner.plan(
        AgentInput(account_id=1, user_input="基于实验 9 写草稿"),
        _router_result(intent=Intent.GENERATE_DRAFT, extracted_params={"account_id": 1, "experiment_id": 9}),
    )

    assert [step.action for step in plan.steps] == [
        Action.QUERY_ACCOUNT_PROFILE,
        Action.QUERY_STRATEGY_MEMORY,
        Action.GENERATE_DRAFT,
        Action.REVIEW_DRAFT,
    ]


def test_task_planner_refine_draft_with_candidate_memory_requires_confirmation():
    """测试明确 Draft 目标时可以规划改稿和候选记忆。"""
    steps = [
        {
            "step_no": 1,
            "action": "REFINE_DRAFT",
            "description": "优化草稿标题。",
            "input_params": {"draft_id": 12, "scope": "title"},
            "expected_output": "标题候选",
            "allowed_effect": "LOCAL_GENERATION",
        },
        {
            "step_no": 2,
            "action": "CREATE_CANDIDATE_MEMORY",
            "description": "暂存用户偏好。",
            "input_params": {"account_id": 1, "source_type": "user_feedback"},
            "depends_on": [1],
            "expected_output": "候选记忆",
            "allowed_effect": "LOCAL_WRITE",
        },
    ]
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload(intent="REFINE_OR_REJECT_RESULT", steps=steps)))

    plan = planner.plan(
        AgentInput(account_id=1, current_target_type=TargetType.DRAFT, current_target_id=12, user_input="标题太普通"),
        _router_result(intent=Intent.REFINE_OR_REJECT_RESULT, target_type=TargetType.DRAFT, target_id=12),
    )

    assert [step.action for step in plan.steps] == [Action.REFINE_DRAFT, Action.CREATE_CANDIDATE_MEMORY]
    assert plan.confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED


def test_task_planner_asks_clarification_when_refine_target_unknown():
    """测试反馈目标未知时生成 ASK_CLARIFICATION。"""
    fake_client = FakeLLMClient(_plan_payload())
    planner = LLMTaskPlanner(fake_client)

    plan = planner.plan(
        AgentInput(user_input="这个不行"),
        _router_result(intent=Intent.REFINE_OR_REJECT_RESULT, target_type=TargetType.UNKNOWN, can_execute=True),
    )

    assert plan.steps[0].action == Action.ASK_CLARIFICATION
    assert plan.confirmation_requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED
    assert fake_client.calls == []


def test_task_planner_missing_params_make_plan_not_executable():
    """测试 missing_params 不为空时 can_execute=false。"""
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload(missing_params=["account_id"], can_execute=True)))

    plan = planner.plan(AgentInput(user_input="帮我找选题"), _router_result())

    assert plan.can_execute is False
    assert RiskFlag.MISSING_REQUIRED_PARAM in plan.risk_flags


def test_task_planner_requires_confirmation_make_plan_not_executable():
    """测试 requires_confirmation=true 时 can_execute=false。"""
    steps = [
        {
            "step_no": 1,
            "action": "GENERATE_CONTENT_OPPORTUNITY",
            "description": "生成内容机会。",
            "input_params": {"account_id": 1},
            "allowed_effect": "LOCAL_GENERATION",
            "requires_confirmation": True,
        }
    ]
    planner = LLMTaskPlanner(FakeLLMClient(_plan_payload(steps=steps)))

    plan = planner.plan(AgentInput(account_id=1, user_input="找选题"), _router_result())

    assert plan.can_execute is False
    assert plan.confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED


def test_task_planner_local_write_requires_user_confirmation():
    """测试 LOCAL_WRITE 动作需要 USER_CONFIRM_REQUIRED。"""
    plan = apply_action_registry_constraints(
        Plan(
            intent=Intent.ANALYZE_COMPETITOR,
            steps=[
                PlanStep(
                    step_no=1,
                    action=Action.ANALYZE_COMPETITOR,
                    description="生成本地竞品分析报告。",
                    input_params={"account_id": 1},
                    allowed_effect=AllowedEffect.READ_ONLY,
                )
            ],
        )
    )

    assert plan.confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED
    assert plan.steps[0].allowed_effect == AllowedEffect.LOCAL_WRITE


def test_task_planner_candidate_memory_requires_user_confirmation():
    """测试 CREATE_CANDIDATE_MEMORY 需要 USER_CONFIRM_REQUIRED。"""
    plan = apply_action_registry_constraints(
        Plan(
            intent=Intent.REFINE_OR_REJECT_RESULT,
            steps=[
                PlanStep(
                    step_no=1,
                    action=Action.CREATE_CANDIDATE_MEMORY,
                    description="暂存候选记忆。",
                    input_params={"account_id": 1},
                    allowed_effect=AllowedEffect.READ_ONLY,
                )
            ],
        )
    )

    assert plan.confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED
    assert RiskFlag.NEEDS_HUMAN_CONFIRMATION in plan.risk_flags


def test_task_planner_external_write_is_blocked():
    """测试 EXTERNAL_WRITE 动作会被 BLOCKED。"""
    planner = LLMTaskPlanner(
        FakeLLMClient(
            _plan_payload(
                steps=[
                    {
                        "step_no": 1,
                        "action": "NOOP",
                        "description": "尝试外部发布。",
                        "allowed_effect": "EXTERNAL_WRITE",
                    }
                ]
            )
        )
    )

    plan = planner.plan(AgentInput(user_input="直接发布"), _router_result())

    assert plan.confirmation_requirement == ConfirmationRequirement.BLOCKED
    assert RiskFlag.EXTERNAL_WRITE in plan.risk_flags


def test_task_planner_destructive_action_is_blocked():
    """测试 DESTRUCTIVE 动作会被 BLOCKED。"""
    planner = LLMTaskPlanner(
        FakeLLMClient(
            _plan_payload(
                steps=[
                    {
                        "step_no": 1,
                        "action": "NOOP",
                        "description": "尝试删除内容。",
                        "allowed_effect": "DESTRUCTIVE",
                    }
                ]
            )
        )
    )

    plan = planner.plan(AgentInput(user_input="删掉这篇"), _router_result())

    assert plan.confirmation_requirement == ConfirmationRequirement.BLOCKED
    assert RiskFlag.DESTRUCTIVE_ACTION in plan.risk_flags


def test_task_planner_invalid_json_returns_safe_plan():
    """测试非法 JSON 返回安全 Plan。"""
    planner = LLMTaskPlanner(FakeLLMClient("not json"))

    plan = planner.plan(AgentInput(user_input="找选题"), _router_result())

    assert plan.can_execute is False
    assert plan.confirmation_requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED
    assert RiskFlag.LOW_CONFIDENCE in plan.risk_flags


def test_task_planner_schema_invalid_returns_safe_plan():
    """测试 Schema 不合法返回安全 Plan。"""
    planner = LLMTaskPlanner(FakeLLMClient(json.dumps({"intent": "GENERATE_DRAFT", "steps": [{"action": "BAD_ACTION"}]})))

    plan = planner.plan(AgentInput(user_input="找选题"), _router_result())

    assert plan.can_execute is False
    assert plan.confirmation_requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED


def test_task_planner_llm_exception_returns_safe_plan():
    """测试 LLMClient 抛异常返回安全 Plan。"""
    planner = LLMTaskPlanner(FakeLLMClient(error=LLMError("LLM_PROVIDER_UNAVAILABLE: down")))

    plan = planner.plan(AgentInput(user_input="找选题"), _router_result())

    assert plan.can_execute is False
    assert plan.next_action == "check_llm_config"


def test_task_planner_prompt_contains_planning_only_constraint():
    """测试 Planner Prompt 包含只规划不执行业务约束。"""
    prompt = build_task_planner_system_prompt()

    assert "只做任务规划，不执行业务" in prompt


def test_task_planner_prompt_contains_action_enum_constraint():
    """测试 Planner Prompt 包含只能选择 Action 枚举约束。"""
    prompt = build_task_planner_system_prompt()

    assert "只能从 Action 枚举中选择动作" in prompt


def test_task_planner_prompt_contains_no_fabrication_constraint():
    """测试 Planner Prompt 包含不能编造 ID 约束。"""
    prompt = build_task_planner_system_prompt()

    assert "不要编造" in prompt


def test_task_planner_does_not_call_business_service_or_workflow():
    """测试 Planner 只调用 LLMClient，不调用业务 service 或 workflow。"""
    fake_client = FakeLLMClient(_plan_payload())
    planner = LLMTaskPlanner(fake_client)

    planner.plan(AgentInput(account_id=1, user_input="找选题"), _router_result())

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["kwargs"]["prompt_key"] == "agent_product_entry.task_planner"
