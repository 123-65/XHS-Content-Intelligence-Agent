from app.agent.product_entry.schemas import ConfirmationCard, ConfirmationRequirement, Plan, PlanValidationResult, RiskFlag


def build_confirmation_card(plan: Plan, plan_validation: PlanValidationResult | None = None) -> ConfirmationCard | None:
    """根据计划和校验结果构造前端确认 / 澄清 / 阻断卡片。"""
    requirement = plan_validation.confirmation_requirement if plan_validation else plan.confirmation_requirement
    risk_flags = plan_validation.risk_flags if plan_validation else plan.risk_flags

    if requirement == ConfirmationRequirement.NONE and plan.can_execute:
        return None
    if requirement == ConfirmationRequirement.CLARIFICATION_REQUIRED:
        return ConfirmationCard(
            title="需要补充信息",
            description=_clarification_description(plan),
            action_type="ASK_CLARIFICATION",
            risk_flags=risk_flags,
            params_preview={"missing_params": plan.missing_params, "next_action": plan.next_action},
            confirm_button_text="补充信息",
            cancel_button_text="取消",
            requires_confirmation=True,
            confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        )
    if requirement == ConfirmationRequirement.BLOCKED:
        return ConfirmationCard(
            title="当前无法执行",
            description=_blocked_description(plan, risk_flags, plan_validation),
            action_type="BLOCKED",
            risk_flags=risk_flags,
            params_preview={"blocked_reason": plan.blocked_reason},
            confirm_button_text="知道了",
            cancel_button_text="取消",
            requires_confirmation=False,
            confirmation_requirement=ConfirmationRequirement.BLOCKED,
        )
    return ConfirmationCard(
        title="请确认执行计划",
        description=_confirmation_description(plan),
        action_type="CONFIRM_PLAN",
        risk_flags=risk_flags,
        params_preview={"steps": [step.action.value for step in plan.steps], "missing_params": plan.missing_params},
        confirm_button_text="确认执行",
        cancel_button_text="取消",
        requires_confirmation=True,
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
    )


def _clarification_description(plan: Plan) -> str:
    """生成澄清卡片说明。"""
    if plan.missing_params:
        return "缺少必要信息：" + "、".join(plan.missing_params)
    return plan.blocked_reason or plan.summary_for_user or "需要先补充信息后才能继续。"


def _confirmation_description(plan: Plan) -> str:
    """生成确认卡片说明。"""
    write_steps = [step.action.value for step in plan.steps if step.requires_confirmation]
    if write_steps:
        return "计划包含需要确认的动作：" + "、".join(write_steps)
    return plan.summary_for_user or "该计划需要你确认后才能进入后续执行。"


def _blocked_description(plan: Plan, risk_flags: list[RiskFlag], plan_validation: PlanValidationResult | None) -> str:
    """生成阻断卡片说明。"""
    if plan_validation and plan_validation.blocked_reason:
        return plan_validation.blocked_reason
    if plan.blocked_reason:
        return plan.blocked_reason
    if risk_flags:
        return "计划包含当前阶段不允许的风险：" + "、".join(flag.value for flag in risk_flags)
    return "当前阶段无法执行该计划。"
