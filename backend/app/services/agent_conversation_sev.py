from typing import Any

from sqlalchemy.orm import Session

from app.agent.product_entry.schemas import AgentChatRequest, AgentChatResponse, ConfirmationRequirement
from app.models.agent_conversation import AgentConversation, AgentConversationMessage
from app.repositories.agent_conversation_repo import AgentConversationRepository
from app.schemas.agent_conversation import (
    ConversationCreate,
    ConversationCurrentState,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationMessageType,
    ConversationPatchState,
    ConversationResponse,
    ConversationRole,
)


class AgentConversationService:
    """Agent 会话与 Current State 业务服务。"""

    def __init__(self, db: Session):
        """初始化 Agent 会话服务。"""
        self.repo = AgentConversationRepository(db)

    def create_conversation(self, data: ConversationCreate) -> ConversationResponse:
        """创建 Agent 会话并初始化 Current State。"""
        state = default_current_state(active_account_id=data.account_id)
        conversation = self.repo.create(data, state.model_dump(mode="json"))
        return self._conversation_response(conversation)

    def list_conversations(self, account_id: int | None = None, limit: int = 30) -> list[ConversationResponse]:
        """查询最近 Agent 会话。"""
        return [self._conversation_response(item) for item in self.repo.list_recent(account_id=account_id, limit=limit)]

    def get_conversation(self, conversation_id: int) -> ConversationResponse:
        """读取 Agent 会话详情。"""
        return self._conversation_response(self._get(conversation_id))

    def list_messages(self, conversation_id: int, limit: int = 30) -> list[ConversationMessageResponse]:
        """读取会话最近消息。"""
        self._get(conversation_id)
        return [ConversationMessageResponse.model_validate(item) for item in self.repo.list_messages(conversation_id, limit=limit)]

    def get_state(self, conversation_id: int) -> ConversationCurrentState:
        """读取会话 Current State。"""
        return _state_from_model(self._get(conversation_id))

    def patch_state(self, conversation_id: int, data: ConversationPatchState) -> ConversationCurrentState:
        """受控更新会话 Current State。"""
        conversation = self._get(conversation_id)
        state = _state_from_model(conversation)
        update = data.model_dump(exclude_unset=True)
        for field, value in update.items():
            if value is not None:
                setattr(state, field, value)
        if data.active_account_id is not None:
            conversation.account_id = data.active_account_id
        updated = self.repo.update_state(conversation, state.model_dump(mode="json"), account_id=state.active_account_id)
        return _state_from_model(updated)

    def prepare_agent_request(self, request: AgentChatRequest, history_limit: int = 20) -> tuple[AgentConversation, AgentChatRequest]:
        """加载会话历史和状态，并合并到 AgentChatRequest。"""
        if request.conversation_id is None:
            raise ValueError("conversation_id is required")
        conversation = self._get(request.conversation_id)
        messages = self.repo.list_messages(conversation.id, limit=history_limit)
        merged_request = merge_request_with_conversation_state(request, _state_from_model(conversation), messages)
        self.save_user_message(conversation, request)
        return conversation, merged_request

    def save_user_message(self, conversation: AgentConversation, request: AgentChatRequest) -> AgentConversationMessage:
        """保存用户消息。"""
        content = request.text or _input_summary(request)
        return self.repo.add_message(
            conversation,
            ConversationMessageCreate(
                role=ConversationRole.USER,
                content=content,
                message_type=ConversationMessageType.TEXT,
                metadata_payload={
                    "input_type": request.input_type.value,
                    "account_id": request.account_id,
                    "current_target_type": request.current_target_type.value if request.current_target_type else None,
                    "current_target_id": request.current_target_id,
                },
            ),
        )

    def save_assistant_message(self, conversation: AgentConversation, response: AgentChatResponse) -> AgentConversationMessage:
        """保存 Agent 回复消息。"""
        return self.repo.add_message(
            conversation,
            ConversationMessageCreate(
                role=ConversationRole.ASSISTANT,
                content=response.message,
                message_type=ConversationMessageType.AGENT_RESPONSE,
                metadata_payload=_assistant_metadata(response),
                trace_id=response.trace_id,
            ),
        )

    def record_agent_response(self, conversation: AgentConversation, request: AgentChatRequest, response: AgentChatResponse) -> AgentChatResponse:
        """保存 Agent 回复并更新 Current State。"""
        self.save_assistant_message(conversation, response)
        state = update_state_from_agent_response(_state_from_model(conversation), request, response)
        updated = self.repo.update_state(conversation, state.model_dump(mode="json"), account_id=state.active_account_id)
        return response.model_copy(
            update={
                "conversation_id": conversation.id,
                "metadata": {
                    **response.metadata,
                    "conversation": {
                        "id": conversation.id,
                        "current_state": _state_from_model(updated).model_dump(mode="json"),
                    },
                },
            }
        )

    def _get(self, conversation_id: int) -> AgentConversation:
        """读取会话，不存在时抛出业务错误。"""
        conversation = self.repo.get(conversation_id)
        if not conversation:
            raise ValueError("conversation does not exist")
        return conversation

    def _conversation_response(self, conversation: AgentConversation) -> ConversationResponse:
        """转换 Conversation ORM 为响应 DTO。"""
        return ConversationResponse(
            id=conversation.id,
            account_id=conversation.account_id,
            title=conversation.title,
            status=conversation.status,
            current_state=_state_from_model(conversation),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message_at=conversation.last_message_at,
        )


def default_current_state(active_account_id: int | None = None) -> ConversationCurrentState:
    """构造 V0 默认 Current State。"""
    return ConversationCurrentState(active_account_id=active_account_id)


def build_agent_context_from_conversation(state: ConversationCurrentState, messages: list[AgentConversationMessage]) -> dict[str, Any]:
    """构造注入 AgentInput context 的会话上下文。"""
    return {
        "current_state": state.model_dump(mode="json"),
        "recent_messages": [
            {
                "role": item.role,
                "content": item.content,
                "message_type": item.message_type,
                "trace_id": item.trace_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in messages
        ],
    }


def merge_request_with_conversation_state(
    request: AgentChatRequest,
    state: ConversationCurrentState,
    messages: list[AgentConversationMessage],
) -> AgentChatRequest:
    """把会话 Current State 合并进本轮请求。"""
    context = {
        **request.context,
        "conversation": build_agent_context_from_conversation(state, messages),
    }
    account_id = request.account_id if request.account_id is not None else state.active_account_id
    current_target_type = request.current_target_type or state.current_target_type
    current_target_id = request.current_target_id if request.current_target_id is not None else state.current_target_id
    return request.model_copy(
        update={
            "account_id": account_id,
            "context": context,
            "current_target_type": current_target_type,
            "current_target_id": current_target_id,
        }
    )


def update_state_from_agent_response(
    state: ConversationCurrentState,
    request: AgentChatRequest,
    response: AgentChatResponse,
) -> ConversationCurrentState:
    """根据本轮请求和 Agent 响应更新 V0 Current State。"""
    next_state = state.model_copy(deep=True)
    if request.account_id is not None:
        next_state.active_account_id = request.account_id
    business_account_id = _business_account_id(response)
    if business_account_id is not None:
        next_state.active_account_id = business_account_id
    _apply_request_target(next_state, request)
    _apply_context_ids(next_state, request.context)
    actions = _response_actions(response)
    if actions:
        next_state.last_action = actions[-1]
    artifact = _response_artifact(response, actions)
    if artifact:
        next_state.last_artifacts = [*next_state.last_artifacts, artifact][-5:]
    if response.requires_confirmation and response.confirmation_card:
        next_state.pending_confirmation = _confirmation_summary(response)
    else:
        next_state.pending_confirmation = None
    constraints = request.context.get("conversation_constraints")
    if isinstance(constraints, dict):
        next_state.conversation_constraints = {**next_state.conversation_constraints, **constraints}
    return next_state


def _state_from_model(conversation: AgentConversation) -> ConversationCurrentState:
    """从 ORM current_state 还原 DTO，并补齐缺失字段。"""
    payload = conversation.current_state or {}
    state = ConversationCurrentState.model_validate(payload)
    if state.active_account_id is None and conversation.account_id is not None:
        state.active_account_id = conversation.account_id
    return state


def _input_summary(request: AgentChatRequest) -> str:
    """生成无文本输入的消息摘要。"""
    return f"{request.input_type.value} input"


def _assistant_metadata(response: AgentChatResponse) -> dict[str, Any]:
    """生成可安全保存的 Assistant 消息摘要。"""
    return {
        "status": response.status.value,
        "trace_id": response.trace_id,
        "intent": response.router_result.intent.value if response.router_result else None,
        "actions": _response_actions(response),
        "risk_flags": _response_risk_flags(response),
        "missing_params": response.router_result.missing_params if response.router_result else [],
    }


def _business_account_id(response: AgentChatResponse) -> int | None:
    """从只读业务结果里提取 account_id。"""
    business_result = response.metadata.get("business_result") if isinstance(response.metadata, dict) else None
    if not isinstance(business_result, dict):
        return None
    if isinstance(business_result.get("account_id"), int):
        return business_result["account_id"]
    profile = business_result.get("account_profile")
    if isinstance(profile, dict) and isinstance(profile.get("account_id"), int):
        return profile["account_id"]
    return None


def _apply_request_target(state: ConversationCurrentState, request: AgentChatRequest) -> None:
    """把本轮明确 target 写入 Current State。"""
    if request.current_target_type:
        state.current_target_type = request.current_target_type.value if hasattr(request.current_target_type, "value") else str(request.current_target_type)
    if request.current_target_id is not None:
        state.current_target_id = request.current_target_id
        if state.current_target_type == "CONTENT_OPPORTUNITY":
            state.active_opportunity_id = _int_or_none(request.current_target_id)
        if state.current_target_type == "CONTENT_EXPERIMENT":
            state.active_experiment_id = _int_or_none(request.current_target_id)
        if state.current_target_type == "DRAFT":
            state.active_draft_id = _int_or_none(request.current_target_id)


def _apply_context_ids(state: ConversationCurrentState, context: dict[str, Any]) -> None:
    """把前端显式传入的对象 ID 写入 Current State。"""
    state.active_opportunity_id = _context_int(context, "opportunity_id") or state.active_opportunity_id
    state.active_experiment_id = _context_int(context, "experiment_id") or state.active_experiment_id
    state.active_draft_id = _context_int(context, "draft_id") or state.active_draft_id


def _response_actions(response: AgentChatResponse) -> list[str]:
    """提取本轮计划动作列表。"""
    if not response.plan:
        return []
    return [step.action.value for step in response.plan.steps]


def _response_risk_flags(response: AgentChatResponse) -> list[str]:
    """提取本轮响应风险标记。"""
    flags: list[str] = []
    if response.router_result:
        flags.extend(flag.value for flag in response.router_result.risk_flags)
    if response.plan:
        flags.extend(flag.value for flag in response.plan.risk_flags)
    if response.plan_validation:
        flags.extend(flag.value for flag in response.plan_validation.risk_flags)
    return list(dict.fromkeys(flags))


def _response_artifact(response: AgentChatResponse, actions: list[str]) -> dict[str, Any] | None:
    """生成 last_artifacts 的轻量摘要。"""
    if not response.trace_id and not actions:
        return None
    business_result = response.metadata.get("business_result") if isinstance(response.metadata, dict) else None
    return {
        "status": response.status.value,
        "trace_id": response.trace_id,
        "intent": response.router_result.intent.value if response.router_result else None,
        "actions": actions,
        "business_result_keys": list(business_result.keys()) if isinstance(business_result, dict) else [],
        "message": response.message,
    }


def _confirmation_summary(response: AgentChatResponse) -> dict[str, Any] | None:
    """生成 pending_confirmation 的安全摘要。"""
    card = response.confirmation_card
    if not card:
        return None
    return {
        "title": card.title,
        "action_type": card.action_type,
        "risk_flags": [flag.value for flag in card.risk_flags],
        "confirmation_requirement": card.confirmation_requirement.value if isinstance(card.confirmation_requirement, ConfirmationRequirement) else str(card.confirmation_requirement),
        "trace_id": response.trace_id,
    }


def _context_int(context: dict[str, Any], key: str) -> int | None:
    """从 context 中安全读取整数 ID。"""
    return _int_or_none(context.get(key))


def _int_or_none(value: Any) -> int | None:
    """把值转换为 int，失败时返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
