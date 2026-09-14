import json
from json import JSONDecodeError
from typing import Any

from pydantic import ValidationError

from app.agent.product_entry.prompts import build_user_input_router_system_prompt, build_user_input_router_user_prompt
from app.agent.product_entry.schemas import (
    AgentChatRequest,
    AgentInput,
    InputAttachment,
    InputType,
    Intent,
    RouterResult,
    TargetType,
)
from app.agent.product_entry.trace import AgentEntryTraceRecorder, AgentEntryTraceStage
from app.agent.product_entry.validators import validate_router_result
from app.llm.errors import LLMError
from app.schemas.provider_status import ProviderErrorCode


class LLMUserInputRouter:
    """LLM 用户输入路由器，只负责把自然语言输入转换成 RouterResult。"""

    def __init__(self, llm_client):
        """初始化路由器，注入已有 LLMClient 或兼容客户端。"""
        self.llm_client = llm_client

    def route(self, agent_input: AgentInput | AgentChatRequest, recorder: AgentEntryTraceRecorder | None = None) -> RouterResult:
        """调用 LLM 识别用户意图，并返回经过校验的 RouterResult。"""
        if self._is_image_only_without_text(agent_input):
            result = validate_router_result(
                RouterResult(
                    intent=Intent.UNKNOWN,
                    confidence=0,
                    input_type=InputType.IMAGE,
                    can_execute=False,
                    requires_clarification=True,
                    next_action="ask_user_to_describe_image_goal",
                    clarification_question="请补充一句这张图要用来做什么。",
                    warning="图片输入未包含文字目标说明，本阶段不做 OCR 或视觉识别。",
                )
            )
            if recorder:
                recorder.record_router_result(result)
            return result

        system_prompt = build_user_input_router_system_prompt()
        prompt_context = self._prompt_context(agent_input)
        user_prompt = build_user_input_router_user_prompt(self._input_text(agent_input), prompt_context)
        if recorder:
            recorder.record_event(
                AgentEntryTraceStage.ROUTER_PROMPT_BUILT,
                summary="Router Prompt 已构建。",
                payload={
                    "system_prompt_length": len(system_prompt),
                    "user_prompt_length": len(user_prompt),
                    "context_keys": list(prompt_context.keys()),
                    "input_type": agent_input.input_type,
                },
            )
        try:
            llm_result = self.llm_client.generate_text(
                user_prompt,
                system_prompt=system_prompt,
                prompt_key="agent_product_entry.llm_router",
                prompt_version="6.2",
            )
        except LLMError as exc:
            result = self._failed_result(agent_input, self._error_code_from_exception(exc), "真实 LLM 不可用，未执行路由。", "check_llm_config")
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=result.intent,
                    error_code=result.error_code,
                    warning=result.warning,
                    summary="Router LLM 调用失败。",
                    payload={"next_action": result.next_action},
                )
            return result
        except Exception:
            result = self._failed_result(agent_input, ProviderErrorCode.LLM_OUTPUT_FAILED.value, "LLM Router 调用失败，未执行路由。", "check_llm_config")
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=result.intent,
                    error_code=result.error_code,
                    warning=result.warning,
                    summary="Router 调用失败。",
                    payload={"next_action": result.next_action},
                )
            return result

        return self._parse_and_validate(self._result_text(llm_result), agent_input, recorder)

    def _parse_and_validate(
        self,
        raw_text: str,
        agent_input: AgentInput | AgentChatRequest,
        recorder: AgentEntryTraceRecorder | None = None,
    ) -> RouterResult:
        """按 JSON 解析、Schema 校验、Router Validator 三层处理 LLM 输出。"""
        try:
            payload = json.loads(raw_text)
        except JSONDecodeError:
            result = self._failed_result(
                agent_input,
                ProviderErrorCode.LLM_OUTPUT_PARSE_FAILED.value,
                "LLM 输出不是合法 JSON。",
                "ask_user_to_retry_or_simplify",
                requires_clarification=True,
            )
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=result.intent,
                    error_code=result.error_code,
                    warning=result.warning,
                    summary="Router 输出 JSON 解析失败。",
                    payload={"raw_text_length": len(raw_text)},
                )
            return result
        if not isinstance(payload, dict):
            result = self._failed_result(
                agent_input,
                ProviderErrorCode.LLM_OUTPUT_PARSE_FAILED.value,
                "LLM 输出 JSON 必须是对象。",
                "ask_user_to_retry_or_simplify",
                requires_clarification=True,
            )
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=result.intent,
                    error_code=result.error_code,
                    warning=result.warning,
                    summary="Router 输出 JSON 不是对象。",
                    payload={"payload_type": type(payload).__name__},
                )
            return result
        try:
            router_result = RouterResult.model_validate(payload)
        except ValidationError:
            result = self._failed_result(
                agent_input,
                ProviderErrorCode.LLM_SCHEMA_INVALID.value,
                "LLM 输出不符合 RouterResult Schema。",
                "ask_user_to_retry_or_simplify",
                requires_clarification=True,
            )
            if recorder:
                recorder.record_event(
                    AgentEntryTraceStage.FAILED,
                    intent=result.intent,
                    error_code=result.error_code,
                    warning=result.warning,
                    summary="RouterResult Schema 校验失败。",
                    payload={"payload_keys": list(payload.keys())},
                )
            return result
        if recorder:
            recorder.record_event(
                AgentEntryTraceStage.ROUTER_RESULT_PARSED,
                intent=router_result.intent,
                risk_flags=router_result.risk_flags,
                missing_params=router_result.missing_params,
                summary="RouterResult 已解析。",
                payload={"confidence": router_result.confidence, "can_execute": router_result.can_execute},
            )
        validated = validate_router_result(router_result)
        if recorder:
            recorder.record_router_result(validated)
        return validated

    def _prompt_context(self, agent_input: AgentInput | AgentChatRequest) -> dict[str, Any]:
        """构建传给 Router Prompt 的入口上下文，只传附件元信息。"""
        return {
            "input_type": agent_input.input_type,
            "attachments": [self._attachment_summary(attachment) for attachment in agent_input.attachments],
            "account_id": agent_input.account_id,
            "current_target_type": self._current_target_type(agent_input),
            "current_target_id": agent_input.current_target_id,
            "context": agent_input.context if isinstance(agent_input, AgentChatRequest) else agent_input.metadata,
        }

    def _attachment_summary(self, attachment: InputAttachment) -> dict[str, Any]:
        """提取附件元信息，不读取图片、文件或 URL 内容。"""
        return {
            "attachment_id": attachment.attachment_id,
            "input_type": attachment.input_type,
            "name": attachment.name,
            "url": attachment.url,
            "mime_type": attachment.mime_type,
            "image_type": attachment.image_type,
            "trust_level": attachment.trust_level,
        }

    def _failed_result(
        self,
        agent_input: AgentInput | AgentChatRequest,
        error_code: str,
        warning: str,
        next_action: str,
        requires_clarification: bool = False,
    ) -> RouterResult:
        """构建安全失败结果，失败时一律不能进入执行。"""
        return RouterResult(
            intent=Intent.UNKNOWN,
            confidence=0,
            input_type=agent_input.input_type,
            can_execute=False,
            requires_clarification=requires_clarification,
            error_code=error_code,
            warning=warning,
            next_action=next_action,
        )

    def _input_text(self, agent_input: AgentInput | AgentChatRequest) -> str | None:
        """兼容 AgentInput 和 AgentChatRequest 的用户文本字段。"""
        return agent_input.text if isinstance(agent_input, AgentChatRequest) else agent_input.user_input

    def _current_target_type(self, agent_input: AgentInput | AgentChatRequest) -> TargetType | None:
        """读取当前交互目标类型，供处理“这个不行”等指代表达。"""
        return agent_input.current_target_type

    def _is_image_only_without_text(self, agent_input: AgentInput | AgentChatRequest) -> bool:
        """判断是否为只有图片且没有文字目标说明的输入。"""
        has_image = agent_input.input_type == InputType.IMAGE or any(attachment.input_type == InputType.IMAGE for attachment in agent_input.attachments)
        return has_image and not (self._input_text(agent_input) or "").strip()

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
