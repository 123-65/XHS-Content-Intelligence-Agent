from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConversationStatus(StrEnum):
    """Agent 会话状态。"""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ConversationRole(StrEnum):
    """Agent 会话消息角色。"""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


class ConversationMessageType(StrEnum):
    """Agent 会话消息类型。"""

    TEXT = "TEXT"
    AGENT_RESPONSE = "AGENT_RESPONSE"
    TOOL_RESULT = "TOOL_RESULT"
    ERROR = "ERROR"


class ConversationCurrentState(BaseModel):
    """会话当前状态，只保存 Agent 连续交互所需的最小上下文。"""

    current_goal: str | None = None
    active_account_id: int | None = None
    active_opportunity_id: int | None = None
    active_experiment_id: int | None = None
    active_draft_id: int | None = None
    current_target_type: str | None = None
    current_target_id: int | str | None = None
    last_action: str | None = None
    last_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    pending_confirmation: dict[str, Any] | None = None
    conversation_constraints: dict[str, Any] = Field(default_factory=dict)
    recent_references: list[dict[str, Any]] = Field(default_factory=list)
    recent_opportunity_collections: list[dict[str, Any]] = Field(default_factory=list)
    recent_review_refs: list[int] = Field(default_factory=list)
    active_pending_run_ref: str | None = None
    active_pending_checkpoint_version: int | None = None
    active_pending_interaction: dict[str, Any] | None = None
    active_pending_semantic_frame: dict[str, Any] | None = None


class ConversationCreate(BaseModel):
    """创建 Agent 会话请求。"""

    account_id: int | None = None
    title: str | None = None


class ConversationPatchState(BaseModel):
    """更新会话当前状态请求，只允许前端更新安全字段。"""

    active_account_id: int | None = None
    active_opportunity_id: int | None = None
    active_experiment_id: int | None = None
    active_draft_id: int | None = None
    current_target_type: str | None = None
    current_target_id: int | str | None = None
    conversation_constraints: dict[str, Any] | None = None


class ConversationResponse(BaseModel):
    """Agent 会话响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    title: str
    status: str
    current_state: ConversationCurrentState
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None


class ConversationMessageCreate(BaseModel):
    """创建会话消息请求。"""

    role: ConversationRole
    content: str
    message_type: ConversationMessageType = ConversationMessageType.TEXT
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ConversationMessageResponse(BaseModel):
    """会话消息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    message_type: str
    metadata_payload: dict[str, Any]
    trace_id: str | None
    created_at: datetime


class ConversationMessagePage(BaseModel):
    """稳定 ID keyset 会话消息页，items 始终按时间正序。"""

    items: list[ConversationMessageResponse]
    next_cursor: int | None = None
    has_more: bool
