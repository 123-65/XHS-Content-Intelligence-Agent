import json
import re
from json import JSONDecodeError
from typing import Any

from pydantic import ValidationError

from app.agent.product_entry.prompts import build_user_input_router_system_prompt, build_user_input_router_user_prompt
from app.agent.product_entry.schemas import (
    Action,
    AgentChatRequest,
    AgentInput,
    InputAttachment,
    InputType,
    Intent,
    RiskFlag,
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
        competitor_collection_result = self._route_competitor_collection_analysis(agent_input, recorder)
        if competitor_collection_result:
            return competitor_collection_result
        deterministic_result = self._route_readonly_query(agent_input, recorder)
        if deterministic_result:
            return deterministic_result
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

    def _route_readonly_query(
        self,
        agent_input: AgentInput | AgentChatRequest,
        recorder: AgentEntryTraceRecorder | None = None,
    ) -> RouterResult | None:
        """对明确的只读查询做确定性路由，不调用真实 LLM。"""
        text = (self._input_text(agent_input) or "").strip()
        actions = _readonly_actions_for_text(text)
        if not text or not actions:
            return None
        account_id = agent_input.account_id
        experiment_id = _context_value(agent_input, "experiment_id")
        user_requirement = _context_value(agent_input, "user_requirement")
        missing_params = []
        if account_id is None:
            missing_params.append("account_id")
        if Action.PREVIEW_DRAFT_CONTEXT in actions and experiment_id is None:
            missing_params.append("experiment_id")
        extracted_params = {"readonly_actions": [action.value for action in actions]}
        if account_id is not None:
            extracted_params["account_id"] = account_id
        if experiment_id is not None:
            extracted_params["experiment_id"] = experiment_id
        if user_requirement:
            extracted_params["user_requirement"] = user_requirement
        result = RouterResult(
            intent=Intent.QUERY_STATUS,
            confidence=0.95,
            input_type=agent_input.input_type,
            target_type=TargetType.ACCOUNT,
            target_id=account_id,
            extracted_params=extracted_params,
            missing_params=missing_params,
            risk_flags=[RiskFlag.MISSING_REQUIRED_PARAM] if missing_params else [],
            requires_clarification=bool(missing_params),
            can_execute=not missing_params,
            next_action=None if not missing_params else "ask_user_to_provide_required_params",
            clarification_question=f"请先补充缺失参数：{', '.join(missing_params)}。" if missing_params else None,
        )
        validated = validate_router_result(result)
        if recorder:
            recorder.record_router_result(validated)
        return validated

    def _route_competitor_collection_analysis(
        self,
        agent_input: AgentInput | AgentChatRequest,
        recorder: AgentEntryTraceRecorder | None = None,
    ) -> RouterResult | None:
        text = (self._input_text(agent_input) or "").strip()
        note_urls = _note_urls_from_input(agent_input, text)
        account_values = _competitor_accounts_from_input(agent_input)
        if not _looks_like_competitor_analysis_request(text) and not (note_urls and account_values):
            return None
        missing_params = []
        if agent_input.account_id is None:
            missing_params.append("account_id")
        if not note_urls:
            missing_params.append("note_urls")
        if not account_values:
            missing_params.append("competitor_account_ids_or_urls")
        result = RouterResult(
            intent=Intent.ANALYZE_COMPETITOR,
            confidence=0.94,
            input_type=agent_input.input_type,
            target_type=TargetType.ACCOUNT,
            target_id=agent_input.account_id,
            extracted_params={
                "account_id": agent_input.account_id,
                "note_urls": note_urls,
                "competitor_account_ids_or_urls": account_values,
                "collect_comments": True,
                "max_comments": 20,
                "enable_ocr": True,
                "recent_note_limit": 10,
                "limit": 20,
            },
            missing_params=missing_params,
            risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT, *([RiskFlag.MISSING_REQUIRED_PARAM] if missing_params else [])],
            requires_clarification=bool(missing_params),
            can_execute=not missing_params,
            next_action=None if not missing_params else "ask_user_to_provide_required_params",
            clarification_question=f"请先补充缺失参数：{', '.join(missing_params)}。" if missing_params else None,
        )
        validated = validate_router_result(result)
        if recorder:
            recorder.record_router_result(validated)
        return validated

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


def _readonly_actions_for_text(text: str) -> list[Action]:
    if not text:
        return []
    actions: list[Action] = []
    if _contains_any(text, ["预览草稿上下文", "查看草稿上下文", "生成草稿前会用哪些资料", "prompt 上下文", "draft context preview", "context preview"]):
        actions.append(Action.PREVIEW_DRAFT_CONTEXT)
    if _contains_any(text, ["查看账号画像", "当前账号画像", "账号信息", "账号定位", "查询账号"]):
        actions.append(Action.QUERY_ACCOUNT_PROFILE)
    if _contains_any(text, ["上下文证据"]):
        actions.extend(
            [
                Action.QUERY_COMPETITOR_EVIDENCE,
                Action.QUERY_COMMENT_INSIGHT,
                Action.QUERY_STRATEGY_MEMORY,
            ]
        )
    else:
        if _contains_any(text, ["竞品证据"]):
            actions.append(Action.QUERY_COMPETITOR_EVIDENCE)
        if _contains_any(text, ["评论洞察", "评论需求"]):
            actions.append(Action.QUERY_COMMENT_INSIGHT)
        if _contains_any(text, ["策略记忆", "历史经验", "记忆"]):
            actions.append(Action.QUERY_STRATEGY_MEMORY)
    return _unique_actions(actions)


def _looks_like_competitor_analysis_request(text: str) -> bool:
    if not text:
        return False
    return _contains_any(text, ["分析这些", "小红书笔记", "同行账号", "竞品分析", "人设", "评论区", "用户需求"])


def _note_urls_from_input(agent_input: AgentInput | AgentChatRequest, text: str) -> list[str]:
    values = []
    context = agent_input.context if isinstance(agent_input, AgentChatRequest) else agent_input.metadata
    raw_context_values = context.get("note_urls") if isinstance(context, dict) else None
    if isinstance(raw_context_values, list):
        values.extend(str(item) for item in raw_context_values)
    for attachment in agent_input.attachments:
        if attachment.metadata.get("attachment_role") == "note_url" and attachment.url:
            values.append(attachment.url)
    values.extend(re.findall(r"https?://[^\s，,]+", text or ""))
    return _unique_texts(value for value in values if "xiaohongshu.com" in value or "xhslink.com" in value)


def _competitor_accounts_from_input(agent_input: AgentInput | AgentChatRequest) -> list[str]:
    values = []
    context = agent_input.context if isinstance(agent_input, AgentChatRequest) else agent_input.metadata
    if isinstance(context, dict):
        raw = context.get("competitor_account_ids_or_urls") or context.get("competitor_account_ids") or context.get("profile_urls")
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
    for attachment in agent_input.attachments:
        if attachment.metadata.get("attachment_role") == "competitor_account_id_or_url":
            value = attachment.metadata.get("value") or attachment.url or attachment.name
            if value:
                values.append(str(value))
    return _unique_texts(values)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _unique_actions(actions: list[Action]) -> list[Action]:
    result: list[Action] = []
    for action in actions:
        if action not in result:
            result.append(action)
    return result


def _unique_texts(values) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _context_value(agent_input: AgentInput | AgentChatRequest, key: str) -> Any:
    if isinstance(agent_input, AgentChatRequest):
        return agent_input.context.get(key)
    context = agent_input.metadata.get("context") if isinstance(agent_input.metadata, dict) else None
    return context.get(key) if isinstance(context, dict) else None
