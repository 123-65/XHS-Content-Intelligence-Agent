from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategyCandidate(Base):
    """发布后复盘派生、可被稳定引用的策略候选。"""

    __tablename__ = "strategy_candidate"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PROPOSED', 'CONFIRMED', 'REJECTED')",
            name="ck_strategy_candidate_status",
        ),
        Index("ix_strategy_candidate_review_source", "review_report_id", "source_candidate_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_report_id: Mapped[int] = mapped_column(
        ForeignKey("review_report.id"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account_profile.id"), nullable=False, index=True
    )
    source_candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_refs: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    contradicting_refs: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    confidence_context: Mapped[str | dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PROPOSED", server_default="PROPOSED", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
