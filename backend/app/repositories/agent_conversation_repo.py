from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_conversation import AgentConversation, AgentConversationMessage
from app.schemas.agent_conversation import ConversationCreate, ConversationMessageCreate


class AgentConversationRepository:
    """Agent 会话数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def create(self, data: ConversationCreate, current_state: dict) -> AgentConversation:
        """创建 Agent 会话。"""
        conversation = AgentConversation(
            account_id=data.account_id,
            title=(data.title or "新会话").strip() or "新会话",
            current_state=current_state,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get(self, conversation_id: int) -> AgentConversation | None:
        """根据 ID 查询会话。"""
        return self.db.get(AgentConversation, conversation_id)

    def list_recent(self, account_id: int | None = None, limit: int = 30) -> list[AgentConversation]:
        """查询最近会话列表。"""
        stmt = select(AgentConversation)
        if account_id is not None:
            stmt = stmt.where(AgentConversation.account_id == account_id)
        stmt = stmt.order_by(AgentConversation.last_message_at.desc().nullslast(), AgentConversation.updated_at.desc(), AgentConversation.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update_state(self, conversation: AgentConversation, current_state: dict, account_id: int | None = None) -> AgentConversation:
        """更新会话 current_state。"""
        conversation.current_state = current_state
        if account_id is not None:
            conversation.account_id = account_id
        conversation.updated_at = _now()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def add_message(self, conversation: AgentConversation, data: ConversationMessageCreate) -> AgentConversationMessage:
        """新增会话消息并更新时间戳。"""
        message = AgentConversationMessage(
            conversation_id=conversation.id,
            role=data.role.value,
            content=data.content,
            message_type=data.message_type.value,
            metadata_payload=data.metadata_payload,
            trace_id=data.trace_id,
        )
        conversation.last_message_at = _now()
        conversation.updated_at = conversation.last_message_at
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        self.db.refresh(conversation)
        return message

    def list_messages(self, conversation_id: int, limit: int = 30, before_id: int | None = None) -> list[AgentConversationMessage]:
        """查询最近消息，按时间正序返回。"""
        stmt = select(AgentConversationMessage).where(AgentConversationMessage.conversation_id == conversation_id)
        if before_id is not None:
            stmt = stmt.where(AgentConversationMessage.id < before_id)
        stmt = stmt.order_by(AgentConversationMessage.id.desc()).limit(limit)
        messages = list(self.db.execute(stmt).scalars().all())
        return list(reversed(messages))


def _now() -> datetime:
    """返回数据库字段使用的朴素 UTC 时间。"""
    return datetime.now(UTC).replace(tzinfo=None)
