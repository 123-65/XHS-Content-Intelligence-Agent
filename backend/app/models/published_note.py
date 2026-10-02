from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PublishedNote(Base):
    """已发布的小红书笔记记录。"""

    __tablename__ = "published_note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="Account ID")
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("content_experiment.id"), nullable=True, comment="Experiment ID")
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_draft.id"), nullable=False, comment="Draft ID")
    draft_version_id: Mapped[int | None] = mapped_column(ForeignKey("content_draft_version.id"), nullable=True, index=True)
    publish_url: Mapped[str] = mapped_column(String(1024), nullable=False, comment="Published note URL")
    platform: Mapped[str] = mapped_column(String(32), default="xhs", nullable=False, comment="Platform")
    status: Mapped[str] = mapped_column(String(32), default="PUBLISHED", nullable=False, comment="Published note status")
    source_type: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False, comment="Source type")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="Published at")
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Raw publish snapshot")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
