from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentDraftVersion(Base):
    """Content draft version snapshot table."""

    __tablename__ = "content_draft_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_draft.id"), nullable=False, comment="Draft ID")
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="Version number")
    regenerate_scope: Mapped[str] = mapped_column(String(32), default="all", nullable=False, comment="Regenerate scope")
    draft_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Draft snapshot")
    prompt_run_log_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_run_log.id"), nullable=True, comment="Prompt run log ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
