from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewReport(Base):
    """内容审核和发布后复盘共用的报告表。"""

    __tablename__ = "review_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_draft.id"), nullable=False, comment="Draft ID")
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account_profile.id"), nullable=True, comment="Account ID")
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("content_experiment.id"), nullable=True, comment="Experiment ID")
    published_note_id: Mapped[int | None] = mapped_column(ForeignKey("published_note.id"), nullable=True, comment="Published note ID")
    review_type: Mapped[str] = mapped_column(String(32), default="CONTENT_REVIEW", nullable=False, comment="Review type")
    result_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="Post-publish result status")
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Content review passed")
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Overall score")
    quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Quality score")
    conversion_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Conversion score")
    evidence_usage_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Evidence usage score")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    issues: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Issues")
    suggestions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Suggestions")
    public_metrics_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Public metrics summary")
    private_conversion_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Private conversion summary")
    comment_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Comment summary")
    data_facts: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Data facts")
    inferences: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Inferences")
    action_suggestions: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Action suggestions")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Summary")
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False, comment="Report status")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Error message")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    raw_response_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Raw response ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
