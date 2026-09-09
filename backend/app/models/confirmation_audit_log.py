from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfirmationAuditLog(Base):
    """Human confirmation audit log table."""

    __tablename__ = "confirmation_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("confirmation_task.id"), nullable=False, comment="Task ID")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Audit event type")
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="Previous status")
    to_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="Next status")
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Actor")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Reason")
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Metadata payload")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
