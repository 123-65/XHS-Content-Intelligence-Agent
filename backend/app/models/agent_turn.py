from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentTurn(Base):
    """Unified Agent API 的最小持久化 Turn 与请求幂等记录。"""

    __tablename__ = "agent_turn"
    __table_args__ = (
        UniqueConstraint("account_id", "client_request_id", name="uq_agent_turn_account_request"),
        Index("ix_agent_turn_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("agent_conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    client_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PROCESSING")
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
