import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.agent.product_entry.schemas import (
    Action,
    AgentChatRequest,
    AgentChatResponse,
    AgentInput,
    AgentResponseStatus,
    ConfirmationCard,
    ConfirmationRequirement,
    InputType,
    Intent,
    ParamValidationResult,
    Plan,
    PlanValidationResult,
    RiskFlag,
    RouterResult,
)


class AgentEntryTraceStage(StrEnum):
    """Agent 入口层 Trace 阶段。"""

    INPUT_RECEIVED = "INPUT_RECEIVED"
    ROUTER_PROMPT_BUILT = "ROUTER_PROMPT_BUILT"
    ROUTER_RESULT_PARSED = "ROUTER_RESULT_PARSED"
    ROUTER_VALIDATED = "ROUTER_VALIDATED"
    PLANNER_PROMPT_BUILT = "PLANNER_PROMPT_BUILT"
    PLAN_PARSED = "PLAN_PARSED"
    PLAN_REGISTRY_APPLIED = "PLAN_REGISTRY_APPLIED"
    PARAM_VALIDATED = "PARAM_VALIDATED"
    PLAN_VALIDATED = "PLAN_VALIDATED"
    CONFIRMATION_CARD_BUILT = "CONFIRMATION_CARD_BUILT"
    RESPONSE_BUILT = "RESPONSE_BUILT"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    STEP_EXECUTION_STARTED = "STEP_EXECUTION_STARTED"
    STEP_EXECUTION_FINISHED = "STEP_EXECUTION_FINISHED"
    EXECUTION_FINISHED = "EXECUTION_FINISHED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    FAILED = "FAILED"


class _TraceSchema(BaseModel):
    """入口层 Trace Schema 基类，禁止额外字段。"""

    model_config = ConfigDict(extra="forbid")


class AgentEntryTraceEvent(_TraceSchema):
    """Agent 入口层单个 Trace 事件。"""

    trace_id: str
    session_id: str | None = None
    stage: AgentEntryTraceStage
    status: AgentResponseStatus | None = None
    intent: Intent | None = None
    action: Action | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    missing_params: list[str] = Field(default_factory=list)
    confirmation_requirement: ConfirmationRequirement | None = None
    error_code: str | None = None
    warning: str | None = None
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentEntryTrace(_TraceSchema):
    """Agent 入口层一次完整请求的 Trace。"""

    trace_id: str
    session_id: str | None = None
    user_id: str | None = None
    account_id: int | None = None
    input_type: InputType = InputType.UNKNOWN
    final_status: AgentResponseStatus | None = None
    final_intent: Intent | None = None
    final_confirmation_requirement: ConfirmationRequirement | None = None
    final_can_execute: bool = False
    events: list[AgentEntryTraceEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|xsec[_-]?token|access[_-]?token|refresh[_-]?token|authorization|cookie|session|password|secret)",
    re.IGNORECASE,
)
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_QUERY_SECRET_RE = re.compile(
    r"(?i)((?:xsec[_-]?token|access[_-]?token|refresh[_-]?token|authorization|session)[=:])([^&\s\"'<>]+)"
)


def mask_sensitive_text(text: str | None) -> str | None:
    """脱敏用户输入或 Prompt 摘要中的敏感内容。"""
    if text is None:
        return None
    masked = _OPENAI_KEY_RE.sub("sk-***", text)
    masked = _BEARER_RE.sub("Bearer ***", masked)
    return _QUERY_SECRET_RE.sub(r"\1***", masked)


def summarize_payload(payload: dict[str, Any] | None, max_chars: int = 800) -> dict[str, Any]:
    """对 Trace payload 做轻量摘要，避免记录过大的原文内容。"""
    if not payload:
        return {}
    return _summarize_value(payload, max_chars)


class AgentEntryTraceRecorder:
    """Agent 入口层 Trace 记录器，先以内存对象组织事件，后续可接数据库 Trace。"""

    def __init__(self, trace_id: str | None = None, session_id: str | None = None):
        """初始化入口层 Trace 记录器。"""
        self.trace_id = trace_id or f"entry_{uuid4().hex}"
        self.session_id = session_id
        self.user_id: str | None = None
        self.account_id: int | None = None
        self.input_type: InputType = InputType.UNKNOWN
        self.final_status: AgentResponseStatus | None = None
        self.final_intent: Intent | None = None
        self.final_confirmation_requirement: ConfirmationRequirement | None = None
        self.final_can_execute = False
        self.created_at = datetime.now(UTC)
        self.updated_at = self.created_at
        self.events: list[AgentEntryTraceEvent] = []

    def record_event(
        self,
        stage: AgentEntryTraceStage,
        status: AgentResponseStatus | None = None,
        intent: Intent | None = None,
        action: Action | None = None,
        risk_flags: list[RiskFlag] | None = None,
        missing_params: list[str] | None = None,
        confirmation_requirement: ConfirmationRequirement | None = None,
        error_code: str | None = None,
        warning: str | None = None,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentEntryTraceEvent:
        """记录一个入口层 Trace 事件。"""
        event = AgentEntryTraceEvent(
            trace_id=self.trace_id,
            session_id=self.session_id,
            stage=stage,
            status=status,
            intent=intent,
            action=action,
            risk_flags=risk_flags or [],
            missing_params=missing_params or [],
            confirmation_requirement=confirmation_requirement,
            error_code=error_code,
            warning=mask_sensitive_text(warning),
            summary=mask_sensitive_text(summary),
            payload=summarize_payload(payload),
        )
        self.events.append(event)
        self.updated_at = event.created_at
        return event

    def record_input(self, agent_input: AgentInput | AgentChatRequest) -> None:
        """记录用户输入摘要。"""
        self.session_id = self.session_id or _session_id(agent_input)
        self.user_id = agent_input.user_id if isinstance(agent_input, AgentChatRequest) else self.user_id
        self.account_id = agent_input.account_id
        self.input_type = agent_input.input_type
        self.record_event(
            AgentEntryTraceStage.INPUT_RECEIVED,
            summary="收到用户输入。",
            payload={
                "input_type": agent_input.input_type,
                "account_id_present": agent_input.account_id is not None,
                "text_summary": mask_sensitive_text(_input_text(agent_input)),
                "text_length": len(_input_text(agent_input) or ""),
                "attachments": [_attachment_summary(item) for item in agent_input.attachments],
                "current_target_type": getattr(agent_input, "current_target_type", None),
                "current_target_id_present": getattr(agent_input, "current_target_id", None) is not None,
            },
        )

    def record_router_result(self, router_result: RouterResult) -> None:
        """记录 Router 输出。"""
        self.final_intent = router_result.intent
        self.record_event(
            AgentEntryTraceStage.ROUTER_VALIDATED,
            intent=router_result.intent,
            risk_flags=router_result.risk_flags,
            missing_params=router_result.missing_params,
            error_code=router_result.error_code,
            warning=router_result.warning,
            summary="RouterResult 已生成并完成校验。",
            payload={
                "confidence": router_result.confidence,
                "input_type": router_result.input_type,
                "target_type": router_result.target_type,
                "target_id_present": router_result.target_id is not None,
                "feedback_action": router_result.feedback_action,
                "requires_clarification": router_result.requires_clarification,
                "requires_confirmation": router_result.requires_confirmation,
                "can_execute": router_result.can_execute,
                "next_action": router_result.next_action,
                "extracted_param_keys": list(router_result.extracted_params.keys()),
            },
        )

    def record_plan(self, plan: Plan, stage: AgentEntryTraceStage = AgentEntryTraceStage.PLAN_PARSED) -> None:
        """记录 Planner 输出。"""
        self.final_intent = plan.intent
        self.final_confirmation_requirement = plan.confirmation_requirement
        self.final_can_execute = plan.can_execute
        self.record_event(
            stage,
            intent=plan.intent,
            risk_flags=plan.risk_flags,
            missing_params=plan.missing_params,
            confirmation_requirement=plan.confirmation_requirement,
            warning=plan.blocked_reason,
            summary="Plan 已生成。",
            payload={
                "steps_count": len(plan.steps),
                "actions": [step.action for step in plan.steps],
                "step_effects": [step.allowed_effect for step in plan.steps],
                "can_execute": plan.can_execute,
                "next_action": plan.next_action,
            },
        )

    def record_param_validation(self, validation: ParamValidationResult) -> None:
        """记录参数校验结果。"""
        self.record_event(
            AgentEntryTraceStage.PARAM_VALIDATED,
            risk_flags=[issue.risk_flag for issue in validation.issues if issue.risk_flag],
            missing_params=validation.missing_params,
            summary="参数校验完成。",
            payload={
                "valid": validation.valid,
                "issues_count": len(validation.issues),
                "issues": [_issue_summary(issue) for issue in validation.issues],
            },
        )

    def record_plan_validation(self, validation: PlanValidationResult) -> None:
        """记录计划校验结果。"""
        self.final_confirmation_requirement = validation.confirmation_requirement
        self.final_can_execute = validation.valid
        self.record_event(
            AgentEntryTraceStage.PLAN_VALIDATED,
            risk_flags=validation.risk_flags,
            confirmation_requirement=validation.confirmation_requirement,
            warning=validation.blocked_reason,
            summary="计划校验完成。",
            payload={
                "valid": validation.valid,
                "issues_count": len(validation.issues),
                "blocked_reason": validation.blocked_reason,
                "issues": [_issue_summary(issue) for issue in validation.issues],
            },
        )

    def record_confirmation_card(self, card: ConfirmationCard | None) -> None:
        """记录确认 / 澄清 / 阻断卡片。"""
        self.record_event(
            AgentEntryTraceStage.CONFIRMATION_CARD_BUILT,
            risk_flags=card.risk_flags if card else [],
            confirmation_requirement=card.confirmation_requirement if card else ConfirmationRequirement.NONE,
            summary="确认卡片已生成。" if card else "当前无需确认卡片。",
            payload={
                "has_card": card is not None,
                "title": card.title if card else None,
                "action_type": card.action_type if card else None,
                "requires_confirmation": card.requires_confirmation if card else False,
                "params_preview_keys": list(card.params_preview.keys()) if card else [],
            },
        )

    def record_response(self, response: AgentChatResponse) -> None:
        """记录最终入口响应状态。"""
        self.final_status = response.status
        self.final_can_execute = response.can_execute
        if response.router_result:
            self.final_intent = response.router_result.intent
        if response.plan:
            self.final_confirmation_requirement = response.plan.confirmation_requirement
        self.record_event(
            AgentEntryTraceStage.RESPONSE_BUILT,
            status=response.status,
            intent=self.final_intent,
            confirmation_requirement=self.final_confirmation_requirement,
            summary="入口层响应已生成。",
            payload={
                "can_execute": response.can_execute,
                "requires_confirmation": response.requires_confirmation,
                "has_confirmation_card": response.confirmation_card is not None,
                "next_action": response.next_action,
                "trace_id": response.trace_id,
            },
        )

    def build_trace(self) -> AgentEntryTrace:
        """构建完整入口层 Trace 对象。"""
        return AgentEntryTrace(
            trace_id=self.trace_id,
            session_id=self.session_id,
            user_id=self.user_id,
            account_id=self.account_id,
            input_type=self.input_type,
            final_status=self.final_status,
            final_intent=self.final_intent,
            final_confirmation_requirement=self.final_confirmation_requirement,
            final_can_execute=self.final_can_execute,
            events=self.events,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


def to_agent_trace_payload(trace: AgentEntryTrace) -> dict[str, Any]:
    """转换为已有 Agent Trace 可接收的轻量 payload。"""
    return {
        "trace_id": trace.trace_id,
        "session_id": trace.session_id,
        "agent_type": "PRODUCT_ENTRY_AGENT",
        "workflow_name": "router_planner_entry",
        "account_id": trace.account_id,
        "input_type": trace.input_type,
        "final_status": trace.final_status,
        "final_intent": trace.final_intent,
        "final_confirmation_requirement": trace.final_confirmation_requirement,
        "final_can_execute": trace.final_can_execute,
        "events": [event.model_dump(mode="json") for event in trace.events],
    }


def _summarize_value(value: Any, max_chars: int) -> Any:
    """递归脱敏并压缩 Trace payload。"""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                result[key_text] = "***"
            else:
                result[key_text] = _summarize_value(item, max_chars)
        return result
    if isinstance(value, list):
        return [_summarize_value(item, max_chars) for item in value[:20]]
    if isinstance(value, tuple):
        return [_summarize_value(item, max_chars) for item in value[:20]]
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, str):
        masked = mask_sensitive_text(value) or ""
        return masked if len(masked) <= max_chars else f"{masked[:max_chars]}...[truncated]"
    return value


def _input_text(agent_input: AgentInput | AgentChatRequest) -> str | None:
    """读取入口层输入文本。"""
    return agent_input.text if isinstance(agent_input, AgentChatRequest) else agent_input.user_input


def _session_id(agent_input: AgentInput | AgentChatRequest) -> str | None:
    """读取入口层会话 ID。"""
    return agent_input.session_id if isinstance(agent_input, AgentChatRequest) else agent_input.conversation_id


def _attachment_summary(attachment) -> dict[str, Any]:
    """记录附件元信息，不记录图片或文件原文。"""
    return {
        "attachment_id": attachment.attachment_id,
        "input_type": attachment.input_type,
        "name": attachment.name,
        "mime_type": attachment.mime_type,
        "image_type": attachment.image_type,
        "trust_level": attachment.trust_level,
        "url_present": attachment.url is not None,
    }


def _issue_summary(issue) -> dict[str, Any]:
    """压缩校验问题，供 Trace 展示。"""
    return {
        "field": issue.field,
        "source": getattr(issue, "source", None),
        "risk_flag": issue.risk_flag,
        "severity": issue.severity,
        "message": issue.message,
        "suggestion": getattr(issue, "suggestion", None),
    }
