from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfirmationTask(Base):
    """Human confirmation task table."""

    __tablename__ = "confirmation_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="Account ID")
    confirmation_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Confirmation type")
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Target type")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Target ID")
    target_version: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Target version")
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False, comment="Task status")
    summary: Mapped[str] = mapped_column(Text, nullable=False, comment="Task summary")
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, comment="System recommendation")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    risk_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Risk reason")
    payload_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Target payload snapshot")
    invalidated_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Invalidated reason")
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Creator")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
