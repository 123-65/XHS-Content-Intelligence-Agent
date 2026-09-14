import pytest

from app.agent.product_entry.execution import ExecutionMode, ExecutionStatus
from app.agent.product_entry.executor import ActionHandlerRegistry, ExecutionOrchestrator, build_response_from_execution
from app.agent.product_entry.schemas import (
    Action,
    AgentResponseStatus,
    AllowedEffect,
    ConfirmationRequirement,
    Intent,
    Plan,
    PlanStep,
    PlanValidationResult,
    RiskFlag,
)
from app.agent.product_entry.trace import AgentEntryTraceRecorder, AgentEntryTraceStage


def _step(step_no=1, action=Action.NOOP, **overrides):
    """构造默认可执行步骤。"""
    data = {
        "step_no": step_no,
        "action": action,
        "description": "测试步骤",
        "allowed_effect": AllowedEffect.READ_ONLY,
        "can_execute": True,
    }
    data.update(overrides)
    return PlanStep(**data)


def _plan(*steps, **overrides):
    """构造默认可执行计划。"""
    data = {
        "intent": Intent.QUERY_STATUS,
        "steps": list(steps) or [_step()],
        "confirmation_requirement": ConfirmationRequirement.NONE,
        "can_execute": True,
    }
    data.update(overrides)
    return Plan(**data)


def test_dry_run_does_not_call_handler():
    """测试 DRY_RUN 不调用 handler。"""
    called = {"value": False}
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: called.update(value=True) or {"ok": True})
    orchestrator = ExecutionOrchestrator(registry)

    result = orchestrator.execute_plan(
        _plan(_step(action=Action.GENERATE_CONTENT_OPPORTUNITY, allowed_effect=AllowedEffect.LOCAL_GENERATION)),
        mode=ExecutionMode.DRY_RUN,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.step_results[0].dry_run is True
    assert called["value"] is False


def test_real_mode_calls_registered_fake_handler():
    """测试 REAL 模式会调用已注册 Fake Handler。"""
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: {"generated": True})
    orchestrator = ExecutionOrchestrator(registry)

    result = orchestrator.execute_plan(
        _plan(_step(action=Action.GENERATE_CONTENT_OPPORTUNITY, allowed_effect=AllowedEffect.LOCAL_GENERATION)),
        mode=ExecutionMode.REAL,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.step_results[0].output == {"generated": True}


def test_unregistered_handler_cannot_execute():
    """测试未注册 handler 的 action 不能执行。"""
    orchestrator = ExecutionOrchestrator()

    result = orchestrator.execute_plan(
        _plan(_step(action=Action.GENERATE_CONTENT_OPPORTUNITY, allowed_effect=AllowedEffect.LOCAL_GENERATION)),
        mode=ExecutionMode.REAL,
    )

    assert result.status == ExecutionStatus.BLOCKED
    assert result.error_code == "HANDLER_NOT_REGISTERED"


def test_plan_can_execute_false_blocks_execution():
    """测试 plan.can_execute=false 时整体 BLOCKED。"""
    result = ExecutionOrchestrator().execute_plan(_plan(can_execute=False), mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.BLOCKED
    assert result.error_code == "PLAN_NOT_EXECUTABLE"


def test_plan_validation_invalid_blocks_execution():
    """测试 plan_validation.valid=false 时整体 BLOCKED。"""
    validation = PlanValidationResult(valid=False, confirmation_requirement=ConfirmationRequirement.NONE, blocked_reason="缺参数")

    result = ExecutionOrchestrator().execute_plan(_plan(), validation, mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.BLOCKED
    assert result.error_code == "PLAN_VALIDATION_FAILED"


def test_user_confirmation_returns_waiting_confirmation():
    """测试 confirmation_requirement=USER_CONFIRM_REQUIRED 时等待确认。"""
    result = ExecutionOrchestrator().execute_plan(
        _plan(confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED),
        mode=ExecutionMode.REAL,
    )

    assert result.status == ExecutionStatus.WAITING_CONFIRMATION


def test_clarification_returns_need_clarification():
    """测试 confirmation_requirement=CLARIFICATION_REQUIRED 时需要澄清。"""
    result = ExecutionOrchestrator().execute_plan(
        _plan(confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED),
        mode=ExecutionMode.REAL,
    )

    assert result.status == ExecutionStatus.NEED_CLARIFICATION


def test_blocked_confirmation_returns_blocked():
    """测试 confirmation_requirement=BLOCKED 时阻断。"""
    result = ExecutionOrchestrator().execute_plan(
        _plan(confirmation_requirement=ConfirmationRequirement.BLOCKED, blocked_reason="风险阻断"),
        mode=ExecutionMode.REAL,
    )

    assert result.status == ExecutionStatus.BLOCKED
    assert result.error_code == "PLAN_BLOCKED"


def test_external_write_step_is_blocked():
    """测试 EXTERNAL_WRITE step 被阻断。"""
    result = ExecutionOrchestrator().execute_plan(_plan(_step(allowed_effect=AllowedEffect.EXTERNAL_WRITE)), mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.BLOCKED
    assert RiskFlag.EXTERNAL_WRITE in result.risk_flags


def test_destructive_step_is_blocked():
    """测试 DESTRUCTIVE step 被阻断。"""
    result = ExecutionOrchestrator().execute_plan(_plan(_step(allowed_effect=AllowedEffect.DESTRUCTIVE)), mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.BLOCKED
    assert RiskFlag.DESTRUCTIVE_ACTION in result.risk_flags


def test_step_requires_confirmation_blocks_execution():
    """测试 step.requires_confirmation=true 时整体不执行。"""
    result = ExecutionOrchestrator().execute_plan(_plan(_step(requires_confirmation=True)), mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.WAITING_CONFIRMATION
    assert result.error_code == "STEP_CONFIRMATION_REQUIRED"


def test_missing_dependency_blocks_execution():
    """测试 depends_on 引用不存在 step 时 BLOCKED。"""
    result = ExecutionOrchestrator().execute_plan(_plan(_step(depends_on=[99])), mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.BLOCKED
    assert result.error_code == "DEPENDENCY_NOT_FOUND"


def test_failed_upstream_skips_downstream_dependency():
    """测试上游 step FAILED 时下游依赖 step SKIPPED。"""
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: (_ for _ in ()).throw(RuntimeError("boom")))
    orchestrator = ExecutionOrchestrator(registry)
    plan = _plan(
        _step(1, Action.GENERATE_CONTENT_OPPORTUNITY, allowed_effect=AllowedEffect.LOCAL_GENERATION),
        _step(2, Action.NOOP, depends_on=[1]),
    )

    result = orchestrator.execute_plan(plan, mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.FAILED
    assert result.step_results[0].status == ExecutionStatus.FAILED
    assert result.step_results[1].status == ExecutionStatus.SKIPPED


def test_handler_exception_marks_step_failed():
    """测试 handler 抛异常时 step FAILED，整体 FAILED。"""
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: (_ for _ in ()).throw(RuntimeError("handler down")))
    orchestrator = ExecutionOrchestrator(registry)

    result = orchestrator.execute_plan(
        _plan(_step(action=Action.GENERATE_CONTENT_OPPORTUNITY, allowed_effect=AllowedEffect.LOCAL_GENERATION)),
        mode=ExecutionMode.REAL,
    )

    assert result.status == ExecutionStatus.FAILED
    assert result.step_results[0].error_code == "HANDLER_FAILED"


def test_noop_default_handler_can_execute():
    """测试 NOOP 默认 handler 可以执行。"""
    result = ExecutionOrchestrator().execute_plan(_plan(_step(action=Action.NOOP)), mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.step_results[0].output["action"] == Action.NOOP.value


def test_ask_clarification_default_handler_returns_question():
    """测试 ASK_CLARIFICATION 默认 handler 返回澄清问题。"""
    plan = _plan(_step(action=Action.ASK_CLARIFICATION, input_params={"question": "缺少账号吗？"}))

    result = ExecutionOrchestrator().execute_plan(plan, mode=ExecutionMode.REAL)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.step_results[0].output["question"] == "缺少账号吗？"


def test_orchestrator_records_execution_started_and_finished():
    """测试 Orchestrator 会记录 EXECUTION_STARTED / EXECUTION_FINISHED。"""
    recorder = AgentEntryTraceRecorder()

    ExecutionOrchestrator().execute_plan(_plan(), mode=ExecutionMode.DRY_RUN, recorder=recorder)

    stages = [event.stage for event in recorder.events]
    assert AgentEntryTraceStage.EXECUTION_STARTED in stages
    assert AgentEntryTraceStage.EXECUTION_FINISHED in stages


def test_orchestrator_records_execution_blocked():
    """测试 Orchestrator 被阻断时记录 EXECUTION_BLOCKED。"""
    recorder = AgentEntryTraceRecorder()

    ExecutionOrchestrator().execute_plan(_plan(can_execute=False), mode=ExecutionMode.REAL, recorder=recorder)

    assert AgentEntryTraceStage.EXECUTION_BLOCKED in [event.stage for event in recorder.events]


def test_build_response_from_execution_waiting_confirmation():
    """测试 build_response_from_execution 能构造 WAITING_CONFIRMATION 响应。"""
    result = ExecutionOrchestrator().execute_plan(
        _plan(confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED),
        mode=ExecutionMode.REAL,
    )

    response = build_response_from_execution(_plan(), result)

    assert response.status == AgentResponseStatus.WAITING_CONFIRMATION
    assert response.requires_confirmation is True


def test_build_response_from_execution_blocked():
    """测试 build_response_from_execution 能构造 BLOCKED 响应。"""
    result = ExecutionOrchestrator().execute_plan(_plan(can_execute=False), mode=ExecutionMode.REAL)

    response = build_response_from_execution(_plan(), result)

    assert response.status == AgentResponseStatus.BLOCKED


def test_build_response_from_execution_failed():
    """测试 build_response_from_execution 能构造 FAILED 响应。"""
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: (_ for _ in ()).throw(RuntimeError("fail")))
    result = ExecutionOrchestrator(registry).execute_plan(
        _plan(_step(action=Action.GENERATE_CONTENT_OPPORTUNITY, allowed_effect=AllowedEffect.LOCAL_GENERATION)),
        mode=ExecutionMode.REAL,
    )

    response = build_response_from_execution(_plan(), result)

    assert response.status == AgentResponseStatus.FAILED


def test_registry_rejects_non_callable_handler():
    """测试 handler 必须是可调用对象。"""
    registry = ActionHandlerRegistry()

    with pytest.raises(ValueError):
        registry.register(Action.NOOP, "not callable")  # type: ignore[arg-type]
