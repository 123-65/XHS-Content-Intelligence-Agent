from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PublishPackage(Base):
    """Manual publish package generated from a final draft."""

    __tablename__ = "publish_package"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_draft.id"), nullable=False, index=True)
    draft_version_id: Mapped[int | None] = mapped_column(ForeignKey("content_draft_version.id"), nullable=True, index=True)
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_report_id: Mapped[int | None] = mapped_column(ForeignKey("review_report.id"), nullable=True, index=True)
    revision_plan_id: Mapped[int | None] = mapped_column(ForeignKey("draft_revision_plan.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), default="ORIGINAL_DRAFT", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="READY", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_card: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    image_cards: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    publish_checklist: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    manual_publish_steps: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
