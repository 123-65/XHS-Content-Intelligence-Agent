import json
from json import JSONDecodeError
from typing import Any

from pydantic import ValidationError

from app.agent.product_entry.prompts import build_task_planner_system_prompt, build_task_planner_user_prompt
from app.agent.product_entry.registry import ACTION_REGISTRY
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
)
from app.agent.product_entry.trace import AgentEntryTraceRecorder, AgentEntryTraceStage
from app.agent.product_entry.validators import validate_plan_result, validate_router_result
from app.llm.errors import LLMError
from app.schemas.provider_status import ProviderErrorCode


class LLMTaskPlanner:
    """LLM 任务规划器，只负责把 RouterResult 转换成结构化 Plan。"""

    def __init__(self, llm_client):
        """初始化任务规划器，注入已有 LLMClient 或兼容客户端。"""
        self.llm_client = llm_client

    def plan(self, agent_input: AgentInput, router_result: RouterResult, recorder: AgentEntryTraceRecorder | None = None) -> Plan:
        """根据用户输入和路由结果生成任务计划，并返回经过校验的 Plan。"""
        checked_router = validate_router_result(router_result)
        if not checked_router.can_execute:
            plan = self._blocked_by_router(agent_input, checked_router)
            if recorder:
                recorder.record_plan(plan, AgentEntryTraceStage.PLAN_VALIDATED)
            return plan
        competitor_collection_plan = self._plan_competitor_collection_analysis(agent_input, checked_router, recorder)
        if competitor_collection_plan:
            return competitor_collection_plan
        deterministic_plan = self._plan_readonly_query(agent_input, checked_router, recorder)
        if deterministic_plan:
            return deterministic_plan

        system_prompt = build_task_planner_system_prompt()
        prompt_context = self._prompt_context(agent_input)
        user_prompt = build_task_planner_user_prompt(checked_router.model_dump(mode="json"), prompt_context)
        if recorder:
            recorder.record_event(
                AgentEntryTraceStage.PLANNER_PROMPT_BUILT,
                intent=checked_router.intent,
                summary="Planner Prompt 已构建。",
                payload={
                    "system_prompt_length": len(system_prompt),
                    "user_prompt_length": len(user_prompt),
                    "context_keys": list(prompt_context.keys()),
                    "router_confidence": checked_router.confidence,
                },
            )
        try:
            llm_result = self.llm_client.generate_text(
                user_prompt,
                system_prompt=system_prompt,
                prompt_key="agent_product_entry.task_planner",
                prompt_version="6.3",
            )
        except LLMError as exc:
            plan = self._safe_plan(
                checked_router.intent,
                f"Planner LLM 调用失败：{self._error_code_from_exception(exc)}。",
                "check_llm_config",
            )
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=checked_router.intent,
                    warning=plan.blocked_reason,
                    summary="Planner LLM 调用失败。",
                    payload={"next_action": plan.next_action},
                )
            return plan
        except Exception:
            plan = self._safe_plan(checked_router.intent, "Planner LLM 调用失败。", "check_llm_config")
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=checked_router.intent,
                    warning=plan.blocked_reason,
                    summary="Planner 调用失败。",
                    payload={"next_action": plan.next_action},
                )
            return plan

        return self._parse_and_validate(self._result_text(llm_result), checked_router, recorder)

    def _plan_readonly_query(
        self,
        agent_input: AgentInput,
        router_result: RouterResult,
        recorder: AgentEntryTraceRecorder | None = None,
    ) -> Plan | None:
        """对只读查询做确定性规划，不调用真实 LLM。"""
        account_id = router_result.extracted_params.get("account_id") or agent_input.account_id
        if router_result.intent != Intent.QUERY_STATUS or router_result.target_type != "ACCOUNT" or account_id is None:
            return None
        actions = _readonly_actions_from_router(router_result) or [Action.QUERY_ACCOUNT_PROFILE]
        experiment_id = router_result.extracted_params.get("experiment_id")
        user_requirement = router_result.extracted_params.get("user_requirement")
        plan = Plan(
            conversation_id=agent_input.conversation_id,
            intent=router_result.intent,
            steps=[
                _readonly_step(
                    index + 1,
                    action,
                    account_id,
                    experiment_id=experiment_id,
                    user_requirement=user_requirement,
                )
                for index, action in enumerate(actions)
            ],
            confirmation_requirement=ConfirmationRequirement.NONE,
            can_execute=True,
            summary_for_user="将执行只读查询，不生成草稿，不写数据库。",
        )
        constrained = apply_action_registry_constraints(plan)
        validated = validate_plan_result(constrained)
        if recorder:
            recorder.record_plan(validated, AgentEntryTraceStage.PLAN_VALIDATED)
        return validated

    def _plan_competitor_collection_analysis(
        self,
        agent_input: AgentInput,
        router_result: RouterResult,
        recorder: AgentEntryTraceRecorder | None = None,
    ) -> Plan | None:
        if router_result.intent != Intent.ANALYZE_COMPETITOR:
            return None
        params = router_result.extracted_params
        note_urls = params.get("note_urls") or []
        account_values = params.get("competitor_account_ids_or_urls") or []
        if not note_urls and not account_values:
            return None
        account_id = params.get("account_id") or agent_input.account_id
        steps: list[PlanStep] = []
        if note_urls:
            steps.append(
                PlanStep(
                    step_no=len(steps) + 1,
                    action=Action.COLLECT_XHS_NOTES,
                    description="采集用户提供的小红书笔记链接、评论、图片和互动指标。",
                    input_params={
                        "account_id": account_id,
                        "note_urls": note_urls,
                        "collect_comments": params.get("collect_comments", True),
                        "max_comments": params.get("max_comments", 10),
                        "enable_ocr": params.get("enable_ocr", True),
                    },
                    expected_output="真实笔记、评论、图片和 OCR 结果入库摘要",
                    allowed_effect=AllowedEffect.EXTERNAL_READ,
                    risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
                    can_execute=True,
                )
            )
        if account_values:
            steps.append(
                PlanStep(
                    step_no=len(steps) + 1,
                    action=Action.COLLECT_XHS_ACCOUNTS,
                    description="采集用户提供的同行账号 ID 或主页链接。",
                    input_params={
                        "account_id": account_id,
                        "competitor_account_ids_or_urls": account_values,
                        "recent_note_limit": params.get("recent_note_limit", 10),
                    },
                    expected_output="真实同行账号和近期笔记入库摘要",
                    allowed_effect=AllowedEffect.EXTERNAL_READ,
                    risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
                    can_execute=True,
                )
            )
        steps.append(
            PlanStep(
                step_no=len(steps) + 1,
                action=Action.ANALYZE_COMPETITOR_DATA,
                description="复用现有竞品分析服务，基于已入库真实数据生成竞品分析结果。",
                input_params={"account_id": account_id, "keyword": params.get("keyword"), "limit": params.get("limit", 20)},
                depends_on=[step.step_no for step in steps],
                expected_output="竞品分析报告、评论需求和内容机会摘要",
                allowed_effect=AllowedEffect.EXTERNAL_READ,
                can_execute=True,
            )
        )
        plan = Plan(
            conversation_id=agent_input.conversation_id,
            intent=router_result.intent,
            steps=steps,
            confirmation_requirement=ConfirmationRequirement.NONE,
            can_execute=True,
            summary_for_user="我会自动采集你提供的真实小红书笔记和同行账号，再生成竞品分析结果。",
        )
        constrained = apply_action_registry_constraints(plan)
        validated = validate_plan_result(constrained)
        if recorder:
            recorder.record_plan(validated, AgentEntryTraceStage.PLAN_VALIDATED)
        return validated

    def _parse_and_validate(self, raw_text: str, router_result: RouterResult, recorder: AgentEntryTraceRecorder | None = None) -> Plan:
        """按 JSON 解析、Plan Schema、Registry 约束、Plan Validator 四层处理 LLM 输出。"""
        try:
            payload = json.loads(raw_text)
        except JSONDecodeError:
            plan = self._safe_plan(router_result.intent, "Planner 输出不是合法 JSON。", "ask_user_to_retry_or_simplify")
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=router_result.intent,
                    warning=plan.blocked_reason,
                    summary="Planner 输出 JSON 解析失败。",
                    payload={"raw_text_length": len(raw_text)},
                )
            return plan
        if not isinstance(payload, dict):
            plan = self._safe_plan(router_result.intent, "Planner 输出 JSON 必须是对象。", "ask_user_to_retry_or_simplify")
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=router_result.intent,
                    warning=plan.blocked_reason,
                    summary="Planner 输出 JSON 不是对象。",
                    payload={"payload_type": type(payload).__name__},
                )
            return plan
        try:
            plan = Plan.model_validate(payload)
        except ValidationError:
            plan = self._safe_plan(router_result.intent, "Planner 输出不符合 Plan Schema。", "ask_user_to_retry_or_simplify")
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=router_result.intent,
                    warning=plan.blocked_reason,
                    summary="Plan Schema 校验失败。",
                    payload={"payload_keys": list(payload.keys())},
                )
            return plan
        if recorder:
            recorder.record_plan(plan, AgentEntryTraceStage.PLAN_PARSED)
        constrained_plan = apply_action_registry_constraints(plan)
        if recorder:
            recorder.record_plan(constrained_plan, AgentEntryTraceStage.PLAN_REGISTRY_APPLIED)
        validated = validate_plan_result(constrained_plan)
        if recorder:
            recorder.record_plan(validated, AgentEntryTraceStage.PLAN_VALIDATED)
        return validated

    def _blocked_by_router(self, agent_input: AgentInput, router_result: RouterResult) -> Plan:
        """Router 已要求澄清或阻断时，Planner 只生成追问计划。"""
        risk_flags = list(router_result.risk_flags)
        if router_result.intent == Intent.UNKNOWN:
            risk_flags = _append_flag(risk_flags, RiskFlag.LOW_CONFIDENCE)
        return validate_plan_result(
            Plan(
                conversation_id=agent_input.conversation_id,
                intent=router_result.intent,
                steps=[
                    PlanStep(
                        step_no=1,
                        action=Action.ASK_CLARIFICATION,
                        description=router_result.clarification_question or "需要先向用户澄清缺失信息或目标对象。",
                        inputs={"missing_params": router_result.missing_params},
                        input_params={"missing_params": router_result.missing_params},
                        expected_output="用户补充信息",
                        allowed_effect=AllowedEffect.READ_ONLY,
                        risk_flags=risk_flags,
                    )
                ],
                missing_params=router_result.missing_params,
                risk_flags=risk_flags,
                confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
                summary_for_user="需要先补充信息，再继续规划任务。",
                blocked_reason=router_result.warning or "RouterResult 当前不可继续规划执行链路。",
                next_action=router_result.next_action or "ask_user_to_clarify",
            )
        )

    def _safe_plan(self, intent: Intent, reason: str, next_action: str) -> Plan:
        """构建安全 Plan，LLM 失败或输出异常时不进入执行。"""
        return validate_plan_result(
            Plan(
                intent=intent,
                steps=[
                    PlanStep(
                        step_no=1,
                        action=Action.ASK_CLARIFICATION,
                        description="Planner 暂时无法生成可靠计划，需要用户重试或简化需求。",
                        inputs={"reason": reason},
                        input_params={"reason": reason},
                        expected_output="用户重新说明需求",
                        allowed_effect=AllowedEffect.READ_ONLY,
                        risk_flags=[RiskFlag.LOW_CONFIDENCE],
                    )
                ],
                risk_flags=[RiskFlag.LOW_CONFIDENCE],
                confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
                blocked_reason=reason,
                next_action=next_action,
            )
        )

    def _prompt_context(self, agent_input: AgentInput) -> dict[str, Any]:
        """构建 Planner Prompt 上下文，只包含入口层必要信息。"""
        return {
            "conversation_id": agent_input.conversation_id,
            "account_id": agent_input.account_id,
            "user_input": agent_input.user_input,
            "input_type": agent_input.input_type,
            "current_target_type": agent_input.current_target_type,
            "current_target_id": agent_input.current_target_id,
            "attachments": [
                {
                    "attachment_id": attachment.attachment_id,
                    "input_type": attachment.input_type,
                    "name": attachment.name,
                    "mime_type": attachment.mime_type,
                    "image_type": attachment.image_type,
                    "trust_level": attachment.trust_level,
                }
                for attachment in agent_input.attachments
            ],
            "metadata": agent_input.metadata,
        }

    def _result_text(self, llm_result) -> str:
        """从 LLMClient 结果中取出文本，兼容测试桩直接返回字符串。"""
        return llm_result if isinstance(llm_result, str) else llm_result.text

    def _error_code_from_exception(self, exc: LLMError) -> str:
        """尽量复用已有 ProviderErrorCode，无法识别时归为 LLM_OUTPUT_FAILED。"""
        message = str(exc)
        for code in ProviderErrorCode:
            if message.startswith(code.value):
                return code.value
        return ProviderErrorCode.LLM_OUTPUT_FAILED.value


def apply_action_registry_constraints(plan: Plan) -> Plan:
    """根据 Action Registry 修正规划结果，防止 LLM 规划不存在或不支持的动作。"""
    risk_flags = _unique_flags(plan.risk_flags)
    missing_params = list(plan.missing_params)
    confirmation_requirement = plan.confirmation_requirement
    blocked_reason = plan.blocked_reason
    steps: list[PlanStep] = []

    for step in plan.steps:
        checked_step, step_missing, step_blocked, step_requires_confirmation, reason = _apply_step_constraints(step)
        steps.append(checked_step)
        for param in step_missing:
            missing_params = _append_text(missing_params, param)
        risk_flags = _merge_flags(risk_flags, checked_step.risk_flags)
        if step_blocked:
            confirmation_requirement = ConfirmationRequirement.BLOCKED
            blocked_reason = blocked_reason or reason
        elif step_requires_confirmation and confirmation_requirement == ConfirmationRequirement.NONE:
            confirmation_requirement = ConfirmationRequirement.USER_CONFIRM_REQUIRED

    if missing_params:
        risk_flags = _append_flag(risk_flags, RiskFlag.MISSING_REQUIRED_PARAM)
    if any(step.allowed_effect in {AllowedEffect.EXTERNAL_WRITE, AllowedEffect.DESTRUCTIVE} for step in plan.steps):
        confirmation_requirement = ConfirmationRequirement.BLOCKED
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
        blocked_reason = blocked_reason or "计划包含当前阶段禁止的高风险动作。"

    return plan.model_copy(
        update={
            "steps": steps,
            "missing_params": missing_params,
            "risk_flags": risk_flags,
            "confirmation_requirement": confirmation_requirement,
            "blocked_reason": blocked_reason,
            "can_execute": not missing_params and confirmation_requirement == ConfirmationRequirement.NONE,
        }
    )


def _readonly_actions_from_router(router_result: RouterResult) -> list[Action]:
    raw_actions = router_result.extracted_params.get("readonly_actions") or []
    if isinstance(raw_actions, str):
        raw_actions = [raw_actions]
    actions: list[Action] = []
    for raw_action in raw_actions:
        try:
            action = Action(raw_action)
        except ValueError:
            continue
        if action in {
            Action.QUERY_ACCOUNT_PROFILE,
            Action.QUERY_COMPETITOR_EVIDENCE,
            Action.QUERY_COMMENT_INSIGHT,
            Action.QUERY_STRATEGY_MEMORY,
        } and action not in actions:
            actions.append(action)
    return actions


def _readonly_step(step_no: int, action: Action, account_id: int, experiment_id: Any = None, user_requirement: Any = None) -> PlanStep:
    descriptions = {
        Action.QUERY_ACCOUNT_PROFILE: ("查询当前账号画像，只读读取 AccountProfile。", "账号画像摘要"),
        Action.QUERY_COMPETITOR_EVIDENCE: ("查询当前账号的竞品证据，只读读取已有报告和机会。", "竞品证据摘要"),
        Action.QUERY_COMMENT_INSIGHT: ("查询当前账号的评论洞察，只读读取已有评论和报告摘要。", "评论洞察摘要"),
        Action.QUERY_STRATEGY_MEMORY: ("查询当前账号的策略记忆，只读读取已有 memory。", "策略记忆摘要"),
    }
    description, expected_output = descriptions[action]
    input_params = {"account_id": account_id}
    return PlanStep(
        step_no=step_no,
        action=action,
        description=description,
        input_params=input_params,
        expected_output=expected_output,
        allowed_effect=AllowedEffect.READ_ONLY,
        can_execute=True,
    )


def _apply_step_constraints(step: PlanStep) -> tuple[PlanStep, list[str], bool, bool, str | None]:
    """把单个步骤对齐到 Action Registry 的能力声明。"""
    capability = ACTION_REGISTRY.get(step.action.value)
    risk_flags = _unique_flags(step.risk_flags)
    step_missing: list[str] = []
    step_blocked = False
    reason = None

    if step.allowed_effect == AllowedEffect.EXTERNAL_WRITE:
        step_blocked = True
        reason = "计划步骤试图执行外部写入动作。"
        risk_flags = _append_flag(risk_flags, RiskFlag.EXTERNAL_WRITE)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
    if step.allowed_effect == AllowedEffect.DESTRUCTIVE:
        step_blocked = True
        reason = "计划步骤试图执行破坏性动作。"
        risk_flags = _append_flag(risk_flags, RiskFlag.DESTRUCTIVE_ACTION)
        risk_flags = _append_flag(risk_flags, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED)
    if not capability or not capability.supported_in_current_stage:
        step_blocked = True
        reason = reason or "计划步骤不在当前支持的 Action Registry 中。"
        risk_flags = _append_flag(risk_flags, RiskFlag.UNSUPPORTED_ACTION)

    allowed_effect = capability.allowed_effect if capability else step.allowed_effect
    required_params = capability.required_params if capability else step.required_params
    input_params = {**step.inputs, **step.input_params}
    for param in required_params:
        if input_params.get(param) is None:
            step_missing = _append_text(step_missing, param)

    requires_confirmation = step.requires_confirmation
    if capability:
        risk_flags = _merge_flags(risk_flags, capability.risk_flags)
        if capability.default_confirmation_requirement == ConfirmationRequirement.USER_CONFIRM_REQUIRED:
            requires_confirmation = True
        if allowed_effect == AllowedEffect.LOCAL_WRITE:
            requires_confirmation = True
            risk_flags = _append_flag(risk_flags, RiskFlag.NEEDS_HUMAN_CONFIRMATION)

    return (
        step.model_copy(
            update={
                "allowed_effect": allowed_effect,
                "required_params": list(required_params),
                "input_params": input_params,
                "risk_flags": risk_flags,
                "requires_confirmation": requires_confirmation,
                "can_execute": not step_blocked and not step_missing and not requires_confirmation,
            }
        ),
        step_missing,
        step_blocked,
        requires_confirmation,
        reason,
    )


def _unique_flags(flags: list[RiskFlag]) -> list[RiskFlag]:
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
