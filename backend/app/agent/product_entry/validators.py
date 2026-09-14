from app.agent.product_entry.registry import ACTION_REGISTRY
from app.agent.product_entry.schemas import (
    Action,
    AllowedEffect,
    ConfirmationRequirement,
    InputType,
    Intent,
    Plan,
    PlanStep,
    RiskFlag,
    RouterResult,
    TargetType,
)


def validate_router_result(result: RouterResult) -> RouterResult:
    """校验 Router 输出，确保低置信、缺参数、未知意图不会被直接执行。"""
    risk_flags = _with_unique_flags(result.risk_flags)
    missing_params = list(result.missing_params)
    requires_clarification = result.requires_clarification
    can_execute = True
    next_action = result.next_action

    if result.intent == Intent.UNKNOWN:
        can_execute = False
    if result.confidence < 0.6:
        can_execute = False
        risk_flags = _append_flag(risk_flags, RiskFlag.LOW_CONFIDENCE)
    if missing_params:
        can_execute = False
        risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
    if result.requires_clarification or result.requires_confirmation:
        can_execute = False
    if result.intent == Intent.REFINE_OR_REJECT_RESULT and result.target_type == TargetType.UNKNOWN:
        can_execute = False
        requires_clarification = True
        risk_flags = _append_flag(risk_flags, RiskFlag.TARGET_AMBIGUOUS)
        missing_params = _append_text(missing_params, "target")
        next_action = next_action or "ask_user_to_clarify_target"
    if result.input_type == InputType.IMAGE and not _has_image_text_description(result):
        can_execute = False
        requires_clarification = True
        next_action = "ask_user_to_describe_image_goal"

    return result.model_copy(
        update={
            "risk_flags": risk_flags,
            "missing_params": missing_params,
            "requires_clarification": requires_clarification,
            "can_execute": can_execute and not requires_clarification,
            "next_action": next_action,
        }
    )


def validate_plan_result(plan: Plan) -> Plan:
    """校验 Planner 输出，确保缺参数、高风险、需确认计划不能直接执行。"""
    risk_flags = _with_unique_flags(plan.risk_flags)
    confirmation_requirement = plan.confirmation_requirement
    blocked_reason = plan.blocked_reason
    can_execute = True
    next_action = plan.next_action
    steps: list[PlanStep] = []

    if not plan.steps:
        can_execute = False
        risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
        next_action = next_action or "ask_planner_to_create_steps"
    if plan.missing_params:
        can_execute = False
        risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
    if confirmation_requirement in {
        ConfirmationRequirement.CLARIFICATION_REQUIRED,
        ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        ConfirmationRequirement.BLOCKED,
    }:
        can_execute = False

    for step in plan.steps:
        checked_step, step_blocks, step_confirmation, step_reason = _validate_step(step)
        steps.append(checked_step)
        if step_blocks:
            can_execute = False
            blocked_reason = blocked_reason or step_reason
        if step_confirmation:
            can_execute = False
            if confirmation_requirement == ConfirmationRequirement.NONE:
                confirmation_requirement = ConfirmationRequirement.USER_CONFIRM_REQUIRED
        risk_flags = _merge_flags(risk_flags, checked_step.risk_flags)

    if any(step.allowed_effect == AllowedEffect.EXTERNAL_WRITE for step in plan.steps):
        confirmation_requirement = ConfirmationRequirement.BLOCKED
        risk_flags = _append_flag(risk_flags, RiskFlag.EXTERNAL_WRITE)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        blocked_reason = blocked_reason or "当前阶段不允许外部写入动作。"
        can_execute = False
    if any(step.allowed_effect == AllowedEffect.DESTRUCTIVE for step in plan.steps):
        confirmation_requirement = ConfirmationRequirement.BLOCKED
        risk_flags = _append_flag(risk_flags, RiskFlag.DESTRUCTIVE_ACTION)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        blocked_reason = blocked_reason or "当前阶段不允许破坏性动作。"
        can_execute = False

    return plan.model_copy(
        update={
            "steps": steps,
            "risk_flags": risk_flags,
            "confirmation_requirement": confirmation_requirement,
            "blocked_reason": blocked_reason,
            "can_execute": can_execute and confirmation_requirement == ConfirmationRequirement.NONE,
            "next_action": next_action,
        }
    )


def _validate_step(step: PlanStep) -> tuple[PlanStep, bool, bool, str | None]:
    """校验单个步骤的能力声明。"""
    risk_flags = _with_unique_flags(step.risk_flags)
    blocks = False
    requires_confirmation = step.requires_confirmation
    reason = None
    capability = ACTION_REGISTRY.get(step.action.value if isinstance(step.action, Action) else str(step.action))

    if not capability or not capability.supported_in_current_stage:
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.UNSUPPORTED_ACTION)
        reason = "计划包含当前阶段不支持的动作。"
    if step.allowed_effect == AllowedEffect.EXTERNAL_WRITE:
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.EXTERNAL_WRITE)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        reason = "计划包含外部写入动作。"
    if step.allowed_effect == AllowedEffect.DESTRUCTIVE:
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.DESTRUCTIVE_ACTION)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        reason = "计划包含破坏性动作。"

    return step.model_copy(update={"risk_flags": risk_flags, "can_execute": not blocks and not requires_confirmation}), blocks, requires_confirmation, reason


def _has_image_text_description(result: RouterResult) -> bool:
    """判断图片输入是否带有文字目标说明。"""
    return bool(result.extracted_params.get("text") or result.extracted_params.get("user_input") or result.extracted_params.get("image_goal"))


def _with_unique_flags(flags: list[RiskFlag]) -> list[RiskFlag]:
    """保持风险标记顺序并去重。"""
    result: list[RiskFlag] = []
    for flag in flags:
        result = _append_flag(result, flag)
    return result


def _append_flag(flags: list[RiskFlag], flag: RiskFlag) -> list[RiskFlag]:
    """追加风险标记并去重。"""
    return flags if flag in flags else [*flags, flag]


def _merge_flags(left: list[RiskFlag], right: list[RiskFlag]) -> list[RiskFlag]:
    """合并风险标记。"""
    result = list(left)
    for flag in right:
        result = _append_flag(result, flag)
    return result


def _append_text(items: list[str], value: str) -> list[str]:
    """追加字符串并去重。"""
    return items if value in items else [*items, value]
