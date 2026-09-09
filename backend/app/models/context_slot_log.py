from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContextSlotLog(Base):
    """Per-slot audit record for a context snapshot."""

    __tablename__ = "context_slot_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    context_snapshot_id: Mapped[int] = mapped_column(ForeignKey("context_snapshot.id"), nullable=False, index=True, comment="Context snapshot ID")
    slot_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="Context slot name")
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="Prompt role")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Source type")
    trust_level: Mapped[str] = mapped_column(String(16), nullable=False, comment="Trust level")
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False, comment="Budget priority")
    original_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Original token estimate")
    injected_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Injected token estimate")
    token_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0, nullable=False, comment="Share of snapshot tokens")
    was_truncated: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Was slot truncated")
    truncation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Truncation reason")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Original slot content hash")
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Governed content preview")
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Slot metadata")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    snapshot: Mapped["ContextSnapshot"] = relationship("ContextSnapshot", back_populates="slot_logs")

