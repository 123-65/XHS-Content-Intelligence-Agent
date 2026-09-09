from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfirmationDecision(Base):
    """Human confirmation decision table."""

    __tablename__ = "confirmation_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("confirmation_task.id"), nullable=False, comment="Task ID")
    decision: Mapped[str] = mapped_column(String(32), nullable=False, comment="Decision")
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Decision maker")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Decision comment")
    revision_request: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Revision request")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
