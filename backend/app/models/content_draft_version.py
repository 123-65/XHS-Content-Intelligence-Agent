from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentDraftVersion(Base):
    """Content draft version snapshot table."""

    __tablename__ = "content_draft_version"
    __table_args__ = (
        CheckConstraint(
            "created_from IS NULL OR created_from IN ('GENERATED', 'REVIEW_REVISION', 'USER_REVISION')",
            name="ck_content_draft_version_created_from",
        ),
        Index("ix_content_draft_version_draft_version", "draft_id", "version"),
        Index(
            "uq_content_draft_version_agent_draft_version",
            "draft_id",
            "version",
            unique=True,
            postgresql_where=text("created_from IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_draft.id"), nullable=False, index=True, comment="Draft Root ID")
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="Version number")
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_draft_version.id"), nullable=True, index=True, comment="Previous Draft Version ID"
    )
    created_from: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="New Agent Version 创建来源")
    regenerate_scope: Mapped[str] = mapped_column(String(32), default="all", nullable=False, comment="Regenerate scope")
    draft_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Draft snapshot")
    prompt_run_log_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_run_log.id"), nullable=True, comment="Prompt run log ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
