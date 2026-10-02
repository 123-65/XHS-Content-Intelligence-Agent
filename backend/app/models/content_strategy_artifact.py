from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentStrategyArtifact(Base):
    """保存由 Research Artifact 派生的结构化内容策略。"""

    __tablename__ = "content_strategy_artifact"
    __table_args__ = (
        Index("ix_content_strategy_artifact_account_created_at", "account_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    research_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("competitor_analysis_report.id"), nullable=False, index=True
    )
    strategy_goal: Mapped[str] = mapped_column(Text, nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    content_directions: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    applicable_constraints: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
