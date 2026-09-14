from typing import Any

from pydantic import ValidationError

from app.agent.product_entry.confirmation import build_confirmation_card
from app.agent.product_entry.execution import ExecutionMode
from app.agent.product_entry.executor import ActionHandlerRegistry, ExecutionOrchestrator, build_response_from_execution
from app.agent.product_entry.registry import ACTION_REGISTRY
from app.agent.product_entry.schemas import (
    Action,
    AgentChatRequest,
    AgentChatResponse,
    AgentInput,
    AgentResponseStatus,
    ConfirmationRequirement,
    InputType,
    Intent,
    ParamValidationResult,
    Plan,
    PlanValidationResult,
    RiskFlag,
    RouterResult,
    TargetType,
    ValidationIssue,
    ValidationSeverity,
)
from app.agent.product_entry.trace import AgentEntryTraceRecorder, AgentEntryTraceStage, to_agent_trace_payload
from app.agent.product_entry.validators import validate_param_sources, validate_plan_params, validate_plan_result


class AgentEntryPreviewPipeline:
    """Agent 入口预览链路，只串联路由、规划、校验、确认卡片和 dry-run 执行。"""

    def __init__(self, router, planner, orchestrator: ExecutionOrchestrator | None = None):
        """初始化入口预览链路，注入 Router、Planner 和 Orchestrator。"""
        self.router = router
        self.planner = planner
        self.orchestrator = orchestrator or build_preview_orchestrator()

    def preview(self, request: AgentChatRequest) -> AgentChatResponse:
        """处理一次 AgentChatRequest，返回不执行业务的 AgentChatResponse。"""
        agent_input = build_agent_input_from_chat_request(request)
        recorder = AgentEntryTraceRecorder(session_id=request.session_id)
        recorder.user_id = request.user_id
        recorder.record_input(agent_input)

        router_result = self._route(agent_input, recorder)
        plan = self._plan(agent_input, router_result, recorder)

        param_validation = validate_plan_params(plan)
        recorder.record_param_validation(param_validation)
        source_validation = validate_param_sources(agent_input, router_result, plan)
        recorder.record_param_validation(source_validation)

        combined_param_validation = merge_param_validation_results(param_validation, source_validation)
        plan = apply_param_validation_to_plan(plan, combined_param_validation)
        plan = validate_plan_result(plan)
        plan_validation = build_plan_validation_result(plan, combined_param_validation)
        recorder.record_plan_validation(plan_validation)

        confirmation_card = build_confirmation_card(plan, plan_validation)
        recorder.record_confirmation_card(confirmation_card)

        execution_result = self.orchestrator.execute_plan(plan, mode=ExecutionMode.DRY_RUN, recorder=recorder)
        response = build_response_from_execution(plan, execution_result, confirmation_card)
        response = response.model_copy(
            update={
                "session_id": request.session_id,
                "router_result": router_result,
                "param_validation": combined_param_validation,
                "plan_validation": plan_validation,
                "trace_id": recorder.trace_id,
                "message": _message_for_response(response, router_result, plan, confirmation_card),
            }
        )
        recorder.record_response(response)
        trace_payload = to_agent_trace_payload(recorder.build_trace())
        return response.model_copy(update={"metadata": {**response.metadata, "entry_trace": trace_payload}})

    def _route(self, agent_input: AgentInput, recorder: AgentEntryTraceRecorder) -> RouterResult:
        """执行 Router 并把非法输出收敛为安全 RouterResult。"""
        try:
            result = self.router.route(agent_input, recorder=recorder)
            if isinstance(result, RouterResult):
                return result
            return RouterResult.model_validate(result)
        except (TypeError, ValueError, ValidationError) as exc:
            safe_result = _safe_router_result(agent_input, "ROUTER_OUTPUT_INVALID", str(exc))
            recorder.record_event(
                AgentEntryTraceStage.FAILED,
                intent=safe_result.intent,
                error_code=safe_result.error_code,
                warning=safe_result.warning,
                summary="Router 输出非法，已收敛为 UNKNOWN。",
            )
            recorder.record_router_result(safe_result)
            return safe_result
        except Exception as exc:
            safe_result = _safe_router_result(agent_input, "ROUTER_FAILED", str(exc))
            recorder.record_event(
                AgentEntryTraceStage.FAILED,
                intent=safe_result.intent,
                error_code=safe_result.error_code,
                warning=safe_result.warning,
                summary="Router 调用失败，已收敛为 UNKNOWN。",
            )
            recorder.record_router_result(safe_result)
            return safe_result

    def _plan(self, agent_input: AgentInput, router_result: RouterResult, recorder: AgentEntryTraceRecorder) -> Plan:
        """执行 Planner 并把非法输出收敛为安全 Plan。"""
        try:
            result = self.planner.plan(agent_input, router_result, recorder=recorder)
            if isinstance(result, Plan):
                return result
            return Plan.model_validate(result)
        except (TypeError, ValueError, ValidationError) as exc:
            safe_plan = _safe_plan(router_result.intent, "PLANNER_OUTPUT_INVALID", str(exc))
            recorder.record_event(
                AgentEntryTraceStage.FAILED,
                intent=safe_plan.intent,
                error_code="PLANNER_OUTPUT_INVALID",
                warning=safe_plan.blocked_reason,
                summary="Planner 输出非法，已生成安全 Plan。",
            )
            recorder.record_plan(safe_plan, AgentEntryTraceStage.PLAN_VALIDATED)
            return safe_plan
        except Exception as exc:
            safe_plan = _safe_plan(router_result.intent, "PLANNER_FAILED", str(exc))
            recorder.record_event(
                AgentEntryTraceStage.FAILED,
                intent=safe_plan.intent,
                error_code="PLANNER_FAILED",
                warning=safe_plan.blocked_reason,
                summary="Planner 调用失败，已生成安全 Plan。",
            )
            recorder.record_plan(safe_plan, AgentEntryTraceStage.PLAN_VALIDATED)
            return safe_plan


def build_agent_input_from_chat_request(request: AgentChatRequest) -> AgentInput:
    """将 AgentChatRequest 转换为入口层 AgentInput。"""
    metadata = {
        "context": request.context,
        "request_metadata": request.metadata,
        "user_id": request.user_id,
    }
    target_id = _target_id(request.current_target_id)
    if request.current_target_id is not None and target_id is None:
        metadata["raw_current_target_id"] = request.current_target_id
    return AgentInput(
        conversation_id=request.session_id,
        account_id=request.account_id,
        user_input=request.text,
        input_type=request.input_type,
        attachments=request.attachments,
        current_target_type=request.current_target_type or TargetType.UNKNOWN,
        current_target_id=target_id,
        metadata=metadata,
    )


def build_preview_orchestrator() -> ExecutionOrchestrator:
    """构造只用于入口预览的 Orchestrator，dry-run 下不会调用任何 handler。"""
    registry = ActionHandlerRegistry()
    for action_name, capability in ACTION_REGISTRY.items():
        if not capability.supported_in_current_stage:
            continue
        action = Action(action_name)
        if registry.is_registered(action):
            continue
        registry.register(action, _preview_handler)
    return ExecutionOrchestrator(registry)


def merge_param_validation_results(*results: ParamValidationResult) -> ParamValidationResult:
    """合并参数完整性校验和参数来源校验结果。"""
    issues: list[ValidationIssue] = []
    missing_params: list[str] = []
    normalized_params: dict[str, Any] = {}
    for result in results:
        issues.extend(result.issues)
        for item in result.missing_params:
            missing_params = _append_text(missing_params, item)
        normalized_params.update(result.normalized_params)
    return ParamValidationResult(
        valid=not issues,
        issues=issues,
        missing_params=missing_params,
        normalized_params=normalized_params,
    )


def apply_param_validation_to_plan(plan: Plan, validation: ParamValidationResult) -> Plan:
    """把参数校验结果反写到 Plan，供确认卡片和 Orchestrator 判断。"""
    risk_flags = _merge_flags(plan.risk_flags, [issue.risk_flag for issue in validation.issues if issue.risk_flag])
    missing_params = list(plan.missing_params)
    for item in validation.missing_params:
        missing_params = _append_text(missing_params, item)

    confirmation_requirement = plan.confirmation_requirement
    blocked_reason = plan.blocked_reason
    next_action = plan.next_action
    if missing_params:
        confirmation_requirement = ConfirmationRequirement.CLARIFICATION_REQUIRED
        blocked_reason = blocked_reason or "计划缺少必要参数，需要先补充信息。"
        next_action = next_action or "ask_user_to_provide_required_params"
    elif not validation.valid and confirmation_requirement == ConfirmationRequirement.NONE:
        confirmation_requirement = ConfirmationRequirement.USER_CONFIRM_REQUIRED
        blocked_reason = blocked_reason or "部分参数来源尚未完全确认，需要用户确认后才能进入真实执行。"
        next_action = next_action or "ask_user_to_confirm_param_sources"

    return plan.model_copy(
        update={
            "missing_params": missing_params,
            "risk_flags": risk_flags,
            "confirmation_requirement": confirmation_requirement,
            "blocked_reason": blocked_reason,
            "next_action": next_action,
            "can_execute": plan.can_execute and validation.valid and confirmation_requirement == ConfirmationRequirement.NONE,
        }
    )


def build_plan_validation_result(plan: Plan, param_validation: ParamValidationResult) -> PlanValidationResult:
    """将最终 Plan 转换为响应层可展示的 PlanValidationResult。"""
    risk_flags = _merge_flags(plan.risk_flags, [issue.risk_flag for issue in param_validation.issues if issue.risk_flag])
    has_clarification = plan.confirmation_requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED
    has_blocker = plan.confirmation_requirement == ConfirmationRequirement.BLOCKED
    blocked_reason = plan.blocked_reason
    if not blocked_reason and param_validation.missing_params:
        blocked_reason = "计划缺少必要参数，需要用户补充后才能继续。"
    return PlanValidationResult(
        valid=not has_clarification and not has_blocker and not param_validation.missing_params,
        confirmation_requirement=plan.confirmation_requirement,
        risk_flags=risk_flags,
        issues=param_validation.issues,
        blocked_reason=blocked_reason,
    )


def _safe_router_result(agent_input: AgentInput, error_code: str, warning: str) -> RouterResult:
    """构造安全 RouterResult，非法 Router 输出不能进入执行。"""
    return RouterResult(
        intent=Intent.UNKNOWN,
        confidence=0,
        input_type=agent_input.input_type or InputType.UNKNOWN,
        can_execute=False,
        requires_clarification=True,
        risk_flags=[RiskFlag.LOW_CONFIDENCE],
        error_code=error_code,
        warning=warning,
        next_action="ask_user_to_retry_or_simplify",
        clarification_question="我还不能可靠理解这次输入，请你换一种更明确的说法。",
    )


def _safe_plan(intent: Intent, error_code: str, warning: str) -> Plan:
    """构造安全 Plan，非法 Planner 输出只允许进入澄清分支。"""
    return Plan(
        intent=intent,
        steps=[],
        risk_flags=[RiskFlag.LOW_CONFIDENCE],
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        can_execute=False,
        blocked_reason=f"{error_code}: {warning}",
        next_action="ask_user_to_retry_or_simplify",
    )


def _message_for_response(
    response: AgentChatResponse,
    router_result: RouterResult,
    plan: Plan,
    confirmation_card,
) -> str:
    """根据最终状态生成入口预览层用户消息。"""
    if response.status == AgentResponseStatus.READY_TO_EXECUTE:
        return "计划已通过校验，本阶段仅预演，不执行业务。"
    if response.status == AgentResponseStatus.NEED_CLARIFICATION:
        return router_result.clarification_question or (confirmation_card.description if confirmation_card else None) or "需要先补充信息后才能继续。"
    if response.status == AgentResponseStatus.WAITING_CONFIRMATION:
        return "计划已生成，但包含需要你确认的动作，本阶段只展示确认卡片和 dry-run 结果。"
    if response.status == AgentResponseStatus.BLOCKED:
        return plan.blocked_reason or (confirmation_card.description if confirmation_card else None) or "当前无法执行该计划。"
    return response.message


def _preview_handler(*args, **kwargs) -> dict[str, Any]:
    """入口预览占位 handler；dry-run 下不会被调用。"""
    return {"preview": True}


def _target_id(value: str | int | None) -> int | None:
    """把前端 current_target_id 规范为 AgentInput 可保存的整数 ID。"""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _append_text(items: list[str], value: str) -> list[str]:
    """追加字符串并保持去重。"""
    return items if value in items else [*items, value]


def _merge_flags(left: list[RiskFlag], right: list[RiskFlag]) -> list[RiskFlag]:
    """合并风险标记并保持顺序。"""
    result = list(left)
    for flag in right:
        if flag and flag not in result:
            result.append(flag)
    return result
