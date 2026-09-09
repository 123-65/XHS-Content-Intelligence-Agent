from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentOptimizationPlan(Base):
    """下一轮内容优化计划。"""

    __tablename__ = "content_optimization_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="Account ID")
    source_review_report_id: Mapped[int] = mapped_column(ForeignKey("review_report.id"), nullable=False, comment="Source review report ID")
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="Plan type")
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", nullable=False, comment="Plan status")
    summary: Mapped[str] = mapped_column(Text, nullable=False, comment="Plan summary")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, comment="Plan rationale")
    actions: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Optimization actions")
    generated_experiment_id: Mapped[int | None] = mapped_column(ForeignKey("content_experiment.id"), nullable=True, comment="Generated experiment ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
