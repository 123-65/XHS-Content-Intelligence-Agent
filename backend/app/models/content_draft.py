from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentDraft(Base):
    """Content draft table."""

    __tablename__ = "content_draft"
    __table_args__ = (
        CheckConstraint(
            "experiment_id IS NOT NULL OR (account_id IS NOT NULL AND strategy_artifact_id IS NOT NULL "
            "AND opportunity_id IS NOT NULL AND content_goal IS NOT NULL)",
            name="ck_content_draft_agent_identity_complete",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("content_experiment.id"), nullable=True, comment="Legacy Experiment ID")
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True, comment="Draft 所属账号 ID")
    strategy_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_strategy_artifact.id"), nullable=True, index=True, comment="New Agent Strategy Artifact ID"
    )
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_opportunity.id"), nullable=True, index=True, comment="New Agent Content Opportunity ID"
    )
    content_goal: Mapped[str | None] = mapped_column(Text, nullable=True, comment="New Agent Draft 不可变内容目标")
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="Legacy note title")
    body: Mapped[str] = mapped_column(Text, nullable=False, comment="Legacy note body")
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Legacy tags")
    cover_text: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="Cover text")
    image_scripts: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Legacy image scripts")
    cta: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Legacy CTA")
    title_candidates: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Title candidates")
    recommended_title: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Recommended title")
    cover_subtitle: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="Cover subtitle")
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Draft body text")
    image_script: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Image script")
    tag_list: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Tag list")
    keyword_list: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Keyword list")
    cta_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="CTA text")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="Draft version")
    status: Mapped[str] = mapped_column(String(32), default="GENERATED", nullable=False, comment="Draft status")
    generation_context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Generation context snapshot")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    raw_response_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Raw LLM response ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
