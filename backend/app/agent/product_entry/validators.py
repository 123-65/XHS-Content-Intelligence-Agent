from typing import Any

from app.agent.product_entry.registry import ACTION_REGISTRY
from app.agent.product_entry.schemas import (
    Action,
    AgentInput,
    AllowedEffect,
    ConfirmationRequirement,
    InputType,
    Intent,
    ParamType,
    ParamValidationResult,
    Plan,
    PlanStep,
    RiskFlag,
    RouterResult,
    TargetType,
    TrustLevel,
    ValidationIssue,
    ValidationSeverity,
)
from app.agent.product_entry.validation_rules import ACTION_ALTERNATIVE_PARAM_GROUPS, ACTION_PARAM_SPECS


_SENSITIVE_ID_PARAMS = {
    "account_id",
    "target_id",
    "draft_id",
    "report_id",
    "experiment_id",
    "content_opportunity_id",
    "competitor_account_id",
    "competitor_note_id",
    "note_snapshot_id",
    "note_id",
    "analytics_snapshot_id",
    "published_note_id",
    "review_report_id",
}
_INSTRUCTION_PARAM_NAMES = {"instruction", "system_rule", "action_override", "tool_override", "developer_instruction"}


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
        if not checked_step.can_execute:
            can_execute = False
        for param in _missing_required_params_for_step(checked_step):
            plan_missing_name = f"step_{checked_step.step_no}.{param}"
            missing_params = plan.missing_params
            if plan_missing_name not in missing_params:
                missing_params = [*missing_params, plan_missing_name]
            plan = plan.model_copy(update={"missing_params": missing_params})
            risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
            can_execute = False

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
            "can_execute": can_execute and confirmation_requirement == ConfirmationRequirement.NONE and not plan.missing_params,
            "next_action": next_action,
            "missing_params": plan.missing_params,
        }
    )


def validate_action_params(action: Action, params: dict[str, Any]) -> ParamValidationResult:
    """根据动作参数规格校验单个 action 的输入参数。"""
    issues: list[ValidationIssue] = []
    missing_params: list[str] = []
    specs = ACTION_PARAM_SPECS.get(action, [])

    for spec in specs:
        value = params.get(spec.name)
        if spec.required and _is_empty(value):
            missing_params = _append_text(missing_params, spec.name)
            issues.append(
                _issue(
                    field=spec.name,
                    message=f"缺少必填参数 {spec.name}。",
                    suggestion=f"请补充 {spec.name}。",
                    risk_flag=RiskFlag.MISSING_REQUIRED_PARAM,
                    source="plan_step",
                    severity=ValidationSeverity.BLOCKER,
                )
            )
            continue
        if not _is_empty(value) and not _matches_param_type(value, spec.param_type):
            issues.append(
                _issue(
                    field=spec.name,
                    message=f"参数 {spec.name} 类型不符合 {spec.param_type.value}。",
                    suggestion=f"请提供合法的 {spec.name}。",
                    risk_flag=RiskFlag.INVALID_PARAM_TYPE,
                    source="plan_step",
                    severity=ValidationSeverity.ERROR,
                )
            )

    for group in ACTION_ALTERNATIVE_PARAM_GROUPS.get(action, []):
        if not any(not _is_empty(params.get(name)) for name in group):
            missing_name = " 或 ".join(group)
            missing_params = _append_text(missing_params, missing_name)
            issues.append(
                _issue(
                    field=missing_name,
                    message=f"缺少二选一参数：{missing_name}。",
                    suggestion=f"请补充 {missing_name} 中的一个。",
                    risk_flag=RiskFlag.MISSING_REQUIRED_PARAM,
                    source="plan_step",
                    severity=ValidationSeverity.BLOCKER,
                )
            )

    return ParamValidationResult(valid=not issues, issues=issues, missing_params=missing_params, normalized_params=dict(params))


def validate_plan_params(plan: Plan) -> ParamValidationResult:
    """校验整个计划的参数完整性和基础类型。"""
    issues: list[ValidationIssue] = []
    missing_params: list[str] = []
    normalized_params: dict[str, Any] = {}

    for step in plan.steps:
        params = _step_params(step)
        result = validate_action_params(step.action, params)
        normalized_params[f"step_{step.step_no}"] = result.normalized_params
        for param in result.missing_params:
            missing_params = _append_text(missing_params, f"step_{step.step_no}.{param}")
        issues.extend(
            issue.model_copy(update={"field": f"step_{step.step_no}.{issue.field}" if issue.field else f"step_{step.step_no}"})
            for issue in result.issues
        )

    return ParamValidationResult(valid=not issues, issues=issues, missing_params=missing_params, normalized_params=normalized_params)


def validate_param_sources(agent_input: AgentInput, router_result: RouterResult, plan: Plan) -> ParamValidationResult:
    """校验关键参数来源，防止 LLM 编造 ID 或把不可信输入当系统指令。"""
    issues: list[ValidationIssue] = []
    trusted_ids = _trusted_id_values(agent_input, router_result)

    for step in plan.steps:
        params = _step_params(step)
        for name, value in params.items():
            if name in _SENSITIVE_ID_PARAMS and not _is_empty(value) and value not in trusted_ids.get(name, set()):
                issues.append(
                    _issue(
                        field=f"step_{step.step_no}.{name}",
                        message=f"参数 {name} 的来源无法确认，可能由 LLM 编造。",
                        suggestion="请让用户确认该 ID，或在后续执行前从可信上下文中解析。",
                        risk_flag=RiskFlag.PARAM_SOURCE_UNVERIFIED,
                        source="plan_step",
                        severity=ValidationSeverity.WARNING,
                    )
                )
                issues.append(
                    _issue(
                        field=f"step_{step.step_no}.{name}",
                        message=f"当前阶段未检查 {name} 指向对象是否真实存在。",
                        suggestion="Executor 前需要通过业务层确认目标存在性。",
                        risk_flag=RiskFlag.TARGET_EXISTENCE_UNCHECKED,
                        source="plan_step",
                        severity=ValidationSeverity.INFO,
                    )
                )
            if _has_untrusted_attachment(agent_input) and name in _INSTRUCTION_PARAM_NAMES and not _is_empty(value):
                issues.append(
                    _issue(
                        field=f"step_{step.step_no}.{name}",
                        message="外部评论、截图或竞品文本疑似被当成系统指令。",
                        suggestion="请只把外部内容作为分析对象，不要作为系统规则或动作覆盖。",
                        risk_flag=RiskFlag.UNTRUSTED_INPUT_USED_AS_INSTRUCTION,
                        source="external_untrusted_input",
                        severity=ValidationSeverity.BLOCKER,
                    )
                )

    return ParamValidationResult(valid=not issues, issues=issues, missing_params=[], normalized_params={})


def _validate_step(step: PlanStep) -> tuple[PlanStep, bool, bool, str | None]:
    """校验单个步骤的能力声明。"""
    risk_flags = _with_unique_flags(step.risk_flags)
    blocks = False
    requires_confirmation = step.requires_confirmation
    reason = None
    capability = ACTION_REGISTRY.get(step.action.value if isinstance(step.action, Action) else str(step.action))
    declared_effect = step.allowed_effect
    allowed_effect = capability.allowed_effect if capability else step.allowed_effect
    required_params = ACTION_PARAM_SPECS.get(step.action, [])
    params = _step_params(step)

    if not capability or not capability.supported_in_current_stage:
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.UNSUPPORTED_ACTION)
        reason = "计划包含当前阶段不支持的动作。"
    if declared_effect == AllowedEffect.EXTERNAL_WRITE or allowed_effect == AllowedEffect.EXTERNAL_WRITE:
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.EXTERNAL_WRITE)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        reason = "计划包含外部写入动作。"
    if declared_effect == AllowedEffect.DESTRUCTIVE or allowed_effect == AllowedEffect.DESTRUCTIVE:
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.DESTRUCTIVE_ACTION)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        reason = "计划包含破坏性动作。"
    if allowed_effect == AllowedEffect.LOCAL_WRITE or step.action == Action.CREATE_CANDIDATE_MEMORY:
        requires_confirmation = True
        risk_flags = _append_flag(risk_flags, RiskFlag.NEEDS_HUMAN_CONFIRMATION)
    if any(_is_empty(params.get(spec.name)) for spec in required_params if spec.required):
        blocks = True
        risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
        reason = reason or "计划步骤缺少必填参数。"
    for group in ACTION_ALTERNATIVE_PARAM_GROUPS.get(step.action, []):
        if not any(not _is_empty(params.get(name)) for name in group):
            blocks = True
            risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
            reason = reason or "计划步骤缺少二选一参数。"
    if RiskFlag.PARAM_SOURCE_UNVERIFIED in risk_flags:
        blocks = True

    return (
        step.model_copy(
            update={
                "allowed_effect": allowed_effect,
                "required_params": [spec.name for spec in required_params if spec.required],
                "input_params": params,
                "risk_flags": risk_flags,
                "requires_confirmation": requires_confirmation,
                "can_execute": not blocks and not requires_confirmation,
            }
        ),
        blocks,
        requires_confirmation,
        reason,
    )


def _has_image_text_description(result: RouterResult) -> bool:
    """判断图片输入是否带有文字目标说明。"""
    return bool(result.extracted_params.get("text") or result.extracted_params.get("user_input") or result.extracted_params.get("image_goal"))


def _missing_required_params_for_step(step: PlanStep) -> list[str]:
    """读取单个步骤缺失的必需参数。"""
    params = _step_params(step)
    missing: list[str] = []
    for spec in ACTION_PARAM_SPECS.get(step.action, []):
        if spec.required and _is_empty(params.get(spec.name)):
            missing = _append_text(missing, spec.name)
    for group in ACTION_ALTERNATIVE_PARAM_GROUPS.get(step.action, []):
        if not any(not _is_empty(params.get(name)) for name in group):
            missing = _append_text(missing, " 或 ".join(group))
    return missing


def _step_params(step: PlanStep) -> dict[str, Any]:
    """合并 PlanStep 的 inputs 和 input_params。"""
    return {**step.inputs, **step.input_params}


def _is_empty(value: Any) -> bool:
    """判断参数是否缺失或为空字符串。"""
    return value is None or (isinstance(value, str) and not value.strip())


def _matches_param_type(value: Any, param_type: ParamType) -> bool:
    """执行轻量参数类型检查，本阶段不做复杂格式校验。"""
    if param_type == ParamType.ANY:
        return True
    if param_type in {ParamType.STRING, ParamType.TEXT, ParamType.DATETIME}:
        return isinstance(value, str) and bool(value.strip())
    if param_type == ParamType.INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if param_type == ParamType.FLOAT:
        return isinstance(value, int | float) and not isinstance(value, bool)
    if param_type == ParamType.BOOL:
        return isinstance(value, bool)
    if param_type == ParamType.ID:
        return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, str) and bool(value.strip()))
    if param_type == ParamType.URL:
        return isinstance(value, str) and value.startswith(("http://", "https://"))
    if param_type == ParamType.LIST:
        return isinstance(value, list)
    if param_type == ParamType.DICT:
        return isinstance(value, dict)
    return True


def _issue(
    field: str | None,
    message: str,
    suggestion: str | None,
    risk_flag: RiskFlag,
    source: str | None,
    severity: ValidationSeverity,
) -> ValidationIssue:
    """构造可给前端解释的校验问题。"""
    return ValidationIssue(
        field=field,
        source=source,
        message=message,
        suggestion=suggestion,
        risk_flag=risk_flag,
        severity=severity,
    )


def _trusted_id_values(agent_input: AgentInput, router_result: RouterResult) -> dict[str, set[Any]]:
    """收集来自 AgentInput 和 RouterResult 的可信 ID 值。"""
    trusted: dict[str, set[Any]] = {name: set() for name in _SENSITIVE_ID_PARAMS}
    if agent_input.account_id is not None:
        trusted["account_id"].add(agent_input.account_id)
    if agent_input.current_target_id is not None:
        trusted["target_id"].add(agent_input.current_target_id)
        if agent_input.current_target_type == TargetType.DRAFT:
            trusted["draft_id"].add(agent_input.current_target_id)
    if router_result.target_id is not None:
        trusted["target_id"].add(router_result.target_id)
        if router_result.target_type == TargetType.DRAFT:
            trusted["draft_id"].add(router_result.target_id)
    for name in _SENSITIVE_ID_PARAMS:
        value = router_result.extracted_params.get(name)
        if value is not None:
            trusted[name].add(value)
    return trusted


def _has_untrusted_attachment(agent_input: AgentInput) -> bool:
    """判断本轮输入是否包含外部不可信附件。"""
    return any(attachment.trust_level == TrustLevel.EXTERNAL_UNTRUSTED for attachment in agent_input.attachments)


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
