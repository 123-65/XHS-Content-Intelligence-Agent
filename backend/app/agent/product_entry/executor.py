from collections.abc import Callable
from typing import Any

from app.agent.product_entry.execution import ExecutionMode, ExecutionStatus, PlanExecutionResult, StepExecutionResult, utc_now
from app.agent.product_entry.registry import ACTION_REGISTRY
from app.agent.product_entry.schemas import (
    Action,
    AgentChatResponse,
    AgentResponseStatus,
    AllowedEffect,
    ConfirmationCard,
    ConfirmationRequirement,
    Plan,
    PlanStep,
    PlanValidationResult,
    RiskFlag,
)
from app.agent.product_entry.trace import AgentEntryTraceRecorder, AgentEntryTraceStage


ActionHandlerFunc = Callable[[PlanStep, dict[str, Any]], dict[str, Any]]


class ActionHandlerRegistry:
    """Action Handler 白名单注册表。"""

    def __init__(self):
        """初始化默认 Handler 白名单。"""
        self._handlers: dict[Action, ActionHandlerFunc] = {}
        self.register(Action.NOOP, _noop_handler)
        self.register(Action.ASK_CLARIFICATION, _ask_clarification_handler)

    def register(self, action: Action, handler: ActionHandlerFunc) -> None:
        """注册某个 Action 的处理器。"""
        if not callable(handler):
            raise ValueError("Action handler must be callable")
        capability = ACTION_REGISTRY.get(action.value)
        if not capability or not capability.supported_in_current_stage:
            raise ValueError(f"Action {action.value} is not supported in current stage")
        if capability.allowed_effect in {AllowedEffect.EXTERNAL_WRITE, AllowedEffect.DESTRUCTIVE}:
            raise ValueError(f"Action {action.value} cannot be registered because it is high risk")
        self._handlers[action] = handler

    def get(self, action: Action) -> ActionHandlerFunc | None:
        """获取某个 Action 的处理器。"""
        return self._handlers.get(action)

    def is_registered(self, action: Action) -> bool:
        """判断 Action 是否已有处理器。"""
        return action in self._handlers


class ExecutionOrchestrator:
    """受控执行编排器，只执行通过校验且已注册 handler 的 PlanStep。"""

    def __init__(self, handler_registry: ActionHandlerRegistry | None = None):
        """初始化执行编排器。"""
        self.handler_registry = handler_registry or ActionHandlerRegistry()

    def execute_plan(
        self,
        plan: Plan,
        plan_validation: PlanValidationResult | None = None,
        mode: ExecutionMode = ExecutionMode.DRY_RUN,
        recorder: AgentEntryTraceRecorder | None = None,
        context: dict[str, Any] | None = None,
    ) -> PlanExecutionResult:
        """执行或 dry-run 一个已校验计划。"""
        if recorder:
            recorder.record_event(
                AgentEntryTraceStage.EXECUTION_STARTED,
                intent=plan.intent,
                confirmation_requirement=plan.confirmation_requirement,
                summary="执行编排开始。",
                payload={"mode": mode, "steps_count": len(plan.steps), "plan_can_execute": plan.can_execute},
            )

        blocked = self._preflight(plan, plan_validation, mode)
        if blocked:
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.EXECUTION_BLOCKED,
                    intent=plan.intent,
                    risk_flags=blocked.risk_flags,
                    confirmation_requirement=blocked.confirmation_requirement,
                    warning=blocked.message,
                    summary="执行编排被阻断。",
                    payload={"error_code": blocked.error_code, "mode": mode},
                )
            return blocked

        if mode == ExecutionMode.DRY_RUN:
            result = self._dry_run(plan, recorder)
            return self._finish(result, recorder)
        result = self._real_run(plan, recorder, context or {})
        return self._finish(result, recorder)

    def _preflight(self, plan: Plan, validation: PlanValidationResult | None, mode: ExecutionMode) -> PlanExecutionResult | None:
        """执行前硬性检查，不通过时不执行任何 step。"""
        if validation and not validation.valid:
            if validation.confirmation_requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED:
                return _blocked_result(plan, mode, ExecutionStatus.NEED_CLARIFICATION, "CLARIFICATION_REQUIRED", validation.blocked_reason or "计划需要先补充信息。", validation.risk_flags)
            if validation.confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED:
                return _blocked_result(plan, mode, ExecutionStatus.WAITING_CONFIRMATION, "CONFIRMATION_REQUIRED", validation.blocked_reason or "计划需要用户确认后才能执行。", validation.risk_flags)
            if validation.confirmation_requirement == ConfirmationRequirement.BLOCKED:
                return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "PLAN_BLOCKED", validation.blocked_reason or "计划已被阻断。", validation.risk_flags)
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "PLAN_VALIDATION_FAILED", validation.blocked_reason or "计划校验未通过。", validation.risk_flags)
        requirement = validation.confirmation_requirement if validation else plan.confirmation_requirement
        if requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED:
            return _blocked_result(plan, mode, ExecutionStatus.WAITING_CONFIRMATION, "CONFIRMATION_REQUIRED", "计划需要用户确认后才能执行。", plan.risk_flags)
        if requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED:
            return _blocked_result(plan, mode, ExecutionStatus.NEED_CLARIFICATION, "CLARIFICATION_REQUIRED", "计划需要先补充信息。", plan.risk_flags)
        if requirement == ConfirmationRequirement.BLOCKED:
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "PLAN_BLOCKED", plan.blocked_reason or "计划已被阻断。", plan.risk_flags)
        if not plan.can_execute:
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "PLAN_NOT_EXECUTABLE", "计划未通过可执行检查。", plan.risk_flags)
        step_orders = {step.step_no for step in plan.steps}
        for step in plan.steps:
            blocked = self._preflight_step(plan, step, step_orders, mode)
            if blocked:
                return blocked
        return None

    def _preflight_step(self, plan: Plan, step: PlanStep, step_orders: set[int], mode: ExecutionMode) -> PlanExecutionResult | None:
        """检查单个步骤是否允许进入 dry-run 或执行。"""
        if not step.can_execute:
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "STEP_NOT_EXECUTABLE", f"步骤 {step.step_no} 不可执行。", step.risk_flags)
        if step.requires_confirmation:
            return _blocked_result(plan, mode, ExecutionStatus.WAITING_CONFIRMATION, "STEP_CONFIRMATION_REQUIRED", f"步骤 {step.step_no} 需要用户确认。", step.risk_flags)
        if step.allowed_effect == AllowedEffect.EXTERNAL_WRITE:
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "EXTERNAL_WRITE_BLOCKED", "当前阶段不允许外部写入。", [*step.risk_flags, RiskFlag.EXTERNAL_WRITE])
        if step.allowed_effect == AllowedEffect.DESTRUCTIVE:
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "DESTRUCTIVE_BLOCKED", "当前阶段不允许破坏性动作。", [*step.risk_flags, RiskFlag.DESTRUCTIVE_ACTION])
        capability = ACTION_REGISTRY.get(step.action.value)
        if not capability or not capability.supported_in_current_stage:
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "UNSUPPORTED_ACTION", f"Action {step.action.value} 当前不支持。", [*step.risk_flags, RiskFlag.UNSUPPORTED_ACTION])
        if not self.handler_registry.is_registered(step.action):
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "HANDLER_NOT_REGISTERED", f"Action {step.action.value} 没有注册 handler。", step.risk_flags)
        if any(dep not in step_orders for dep in step.depends_on):
            return _blocked_result(plan, mode, ExecutionStatus.BLOCKED, "DEPENDENCY_NOT_FOUND", f"步骤 {step.step_no} 依赖不存在的 step。", step.risk_flags)
        return None

    def _dry_run(self, plan: Plan, recorder: AgentEntryTraceRecorder | None) -> PlanExecutionResult:
        """dry-run 模式只返回将要执行的步骤，不调用 handler。"""
        step_results = [
            StepExecutionResult(
                step_order=step.step_no,
                action=step.action,
                status=ExecutionStatus.SKIPPED,
                can_execute=True,
                dry_run=True,
                message="DRY_RUN 模式不调用 handler。",
                risk_flags=step.risk_flags,
            )
            for step in _sorted_steps(plan)
        ]
        if recorder:
            for item in step_results:
                recorder.record_event(
                    AgentEntryTraceStage.STEP_EXECUTION_FINISHED,
                    action=item.action,
                    risk_flags=item.risk_flags,
                    summary="dry-run 步骤已跳过真实执行。",
                    payload={"step_order": item.step_order, "status": item.status, "dry_run": True},
                )
        return PlanExecutionResult(
            plan_id=plan.plan_id,
            session_id=plan.conversation_id,
            trace_id=recorder.trace_id if recorder else None,
            status=ExecutionStatus.SUCCESS,
            mode=ExecutionMode.DRY_RUN,
            can_execute=True,
            step_results=step_results,
            message="DRY_RUN 完成，未调用任何业务 handler。",
            confirmation_requirement=ConfirmationRequirement.NONE,
        )

    def _real_run(self, plan: Plan, recorder: AgentEntryTraceRecorder | None, context: dict[str, Any]) -> PlanExecutionResult:
        """REAL 模式只调用已注册 handler，并处理依赖和异常。"""
        step_results: list[StepExecutionResult] = []
        success_steps: set[int] = set()
        result_by_step: dict[int, StepExecutionResult] = {}
        failed = False

        for step in _sorted_steps(plan):
            if any(dep not in success_steps for dep in step.depends_on):
                skipped = _step_result(step, ExecutionStatus.SKIPPED, "上游依赖未成功，跳过当前步骤。")
                step_results.append(skipped)
                result_by_step[step.step_no] = skipped
                self._record_step_finished(recorder, skipped)
                continue
            started = utc_now()
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.STEP_EXECUTION_STARTED,
                    action=step.action,
                    risk_flags=step.risk_flags,
                    summary="步骤开始执行。",
                    payload={"step_order": step.step_no},
                )
            try:
                output = self.handler_registry.get(step.action)(step, context)  # type: ignore[misc]
                finished = _step_result(step, ExecutionStatus.SUCCESS, "步骤执行完成。", output, started_at=started, finished_at=utc_now(), dry_run=False)
                success_steps.add(step.step_no)
            except Exception as exc:
                finished = _step_result(step, ExecutionStatus.FAILED, str(exc), error_code="HANDLER_FAILED", started_at=started, finished_at=utc_now(), dry_run=False)
                failed = True
            step_results.append(finished)
            result_by_step[step.step_no] = finished
            self._record_step_finished(recorder, finished)

        return PlanExecutionResult(
            plan_id=plan.plan_id,
            session_id=plan.conversation_id,
            trace_id=recorder.trace_id if recorder else None,
            status=ExecutionStatus.FAILED if failed else ExecutionStatus.SUCCESS,
            mode=ExecutionMode.REAL,
            can_execute=not failed,
            step_results=step_results,
            output={"successful_steps": len(success_steps), "total_steps": len(step_results)},
            error_code="STEP_FAILED" if failed else None,
            message="执行失败。" if failed else "执行完成。",
            risk_flags=plan.risk_flags,
            confirmation_requirement=ConfirmationRequirement.NONE,
        )

    def _record_step_finished(self, recorder: AgentEntryTraceRecorder | None, result: StepExecutionResult) -> None:
        """记录单步执行完成事件。"""
        if not recorder:
            return
        recorder.record_event(
            AgentEntryTraceStage.STEP_EXECUTION_FINISHED,
            action=result.action,
            risk_flags=result.risk_flags,
            error_code=result.error_code,
            warning=result.message if result.status == ExecutionStatus.FAILED else None,
            summary="步骤执行结束。",
            payload={"step_order": result.step_order, "status": result.status, "dry_run": result.dry_run},
        )

    def _finish(self, result: PlanExecutionResult, recorder: AgentEntryTraceRecorder | None) -> PlanExecutionResult:
        """记录执行完成事件并返回结果。"""
        if recorder:
            recorder.record_event(
                AgentEntryTraceStage.EXECUTION_FINISHED,
                risk_flags=result.risk_flags,
                confirmation_requirement=result.confirmation_requirement,
                error_code=result.error_code,
                warning=result.message if result.status in {ExecutionStatus.FAILED, ExecutionStatus.BLOCKED} else None,
                summary="执行编排结束。",
                payload={"status": result.status, "mode": result.mode, "steps_count": len(result.step_results)},
            )
        return result


def build_response_from_execution(
    plan: Plan,
    execution_result: PlanExecutionResult,
    confirmation_card: ConfirmationCard | None = None,
) -> AgentChatResponse:
    """根据执行结果构造入口层统一响应。"""
    success_status = AgentResponseStatus.SUCCESS if execution_result.mode == ExecutionMode.REAL else AgentResponseStatus.READY_TO_EXECUTE
    status_mapping = {
        ExecutionStatus.SUCCESS: success_status,
        ExecutionStatus.WAITING_CONFIRMATION: AgentResponseStatus.WAITING_CONFIRMATION,
        ExecutionStatus.NEED_CLARIFICATION: AgentResponseStatus.NEED_CLARIFICATION,
        ExecutionStatus.BLOCKED: AgentResponseStatus.BLOCKED,
        ExecutionStatus.FAILED: AgentResponseStatus.FAILED,
        ExecutionStatus.SKIPPED: AgentResponseStatus.FAILED,
        ExecutionStatus.NOT_STARTED: AgentResponseStatus.PLANNED,
    }
    return AgentChatResponse(
        session_id=execution_result.session_id,
        plan=plan,
        confirmation_card=confirmation_card,
        status=status_mapping[execution_result.status],
        can_execute=execution_result.can_execute,
        requires_confirmation=execution_result.status == ExecutionStatus.WAITING_CONFIRMATION,
        message=execution_result.message or "执行编排完成。",
        next_action=_next_action_for_execution(execution_result.status),
        trace_id=execution_result.trace_id,
        metadata={"execution": execution_result.model_dump(mode="json")},
    )


def _blocked_result(
    plan: Plan,
    mode: ExecutionMode,
    status: ExecutionStatus,
    error_code: str,
    message: str,
    risk_flags: list[RiskFlag],
) -> PlanExecutionResult:
    """构造整体阻断结果。"""
    return PlanExecutionResult(
        plan_id=plan.plan_id,
        session_id=plan.conversation_id,
        status=status,
        mode=mode,
        can_execute=False,
        error_code=error_code,
        message=message,
        risk_flags=_unique_flags(risk_flags),
        confirmation_requirement=plan.confirmation_requirement,
    )


def _step_result(
    step: PlanStep,
    status: ExecutionStatus,
    message: str,
    output: dict[str, Any] | None = None,
    error_code: str | None = None,
    started_at=None,
    finished_at=None,
    dry_run: bool = False,
) -> StepExecutionResult:
    """构造单步执行结果。"""
    return StepExecutionResult(
        step_order=step.step_no,
        action=step.action,
        status=status,
        can_execute=status == ExecutionStatus.SUCCESS,
        dry_run=dry_run,
        output=output or {},
        error_code=error_code,
        message=message,
        risk_flags=step.risk_flags,
        started_at=started_at,
        finished_at=finished_at,
    )


def _sorted_steps(plan: Plan) -> list[PlanStep]:
    """按 step_order 升序返回步骤。"""
    return sorted(plan.steps, key=lambda step: step.step_no)


def _noop_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """默认 NOOP handler，不执行业务动作。"""
    return {"ok": True, "action": step.action.value, "message": "NOOP completed"}


def _ask_clarification_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """默认 ASK_CLARIFICATION handler，只返回澄清问题。"""
    question = step.input_params.get("question") or step.inputs.get("question") or step.description
    return {"question": question, "missing_params": step.input_params.get("missing_params") or step.inputs.get("missing_params") or []}


def _next_action_for_execution(status: ExecutionStatus) -> str | None:
    """根据执行状态给出入口层下一步建议。"""
    mapping = {
        ExecutionStatus.WAITING_CONFIRMATION: "show_confirmation_card",
        ExecutionStatus.NEED_CLARIFICATION: "ask_user_to_clarify",
        ExecutionStatus.BLOCKED: "explain_execution_blocked",
        ExecutionStatus.FAILED: "show_execution_error",
    }
    return mapping.get(status)


def _unique_flags(flags: list[RiskFlag]) -> list[RiskFlag]:
    """保持风险标记顺序并去重。"""
    result: list[RiskFlag] = []
    for flag in flags:
        if flag not in result:
            result.append(flag)
    return result
