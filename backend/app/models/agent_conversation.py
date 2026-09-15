from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentConversation(Base):
    """Agent 产品入口会话。"""

    __tablename__ = "agent_conversation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account_profile.id"), nullable=True, index=True, comment="Active account ID")
    title: Mapped[str] = mapped_column(String(128), default="新会话", nullable=False, comment="Conversation title")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, index=True, comment="Conversation status")
    current_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Current conversation state")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True, comment="Last message time")

    messages: Mapped[list["AgentConversationMessage"]] = relationship(
        "AgentConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AgentConversationMessage(Base):
    """Agent 产品入口会话消息。"""

    __tablename__ = "agent_conversation_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("agent_conversation.id", ondelete="CASCADE"), nullable=False, index=True, comment="Conversation ID")
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="Message role")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Message content")
    message_type: Mapped[str] = mapped_column(String(32), default="TEXT", nullable=False, index=True, comment="Message type")
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Safe message metadata")
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="Agent trace ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)

    conversation: Mapped[AgentConversation] = relationship("AgentConversation", back_populates="messages")
