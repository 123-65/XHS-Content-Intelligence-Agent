from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DraftRevisionPlan(Base):
    """Controlled B10 revision plan for an existing draft."""

    __tablename__ = "draft_revision_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_draft.id"), nullable=False, index=True)
    review_report_id: Mapped[int | None] = mapped_column(ForeignKey("review_report.id"), nullable=True, index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("agent_conversation.id"), nullable=True, index=True)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_scope: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="READY", nullable=False, index=True)
    plan: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_flags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    base_draft_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
