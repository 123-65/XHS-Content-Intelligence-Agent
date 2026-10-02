from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentOpportunity(Base):
    """内容机会表。"""

    __tablename__ = "content_opportunity"
    __table_args__ = (
        CheckConstraint(
            "strategy_artifact_id IS NULL OR ("
            "source_opportunity_id IS NOT NULL AND content_goal IS NOT NULL AND why_now IS NOT NULL AND "
            "suggested_hook IS NOT NULL AND evidence_refs IS NOT NULL AND constraints IS NOT NULL)",
            name="ck_content_opportunity_strategy_fields_complete",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("competitor_analysis_report.id"), nullable=False, index=True, comment="竞品分析报告 ID")
    strategy_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_strategy_artifact.id"), nullable=True, index=True, comment="派生该机会的内容策略 Artifact ID"
    )
    source_opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_opportunity.id"), nullable=True, index=True, comment="Strategy Opportunity 对应的 Research Opportunity ID"
    )
    opportunity_title: Mapped[str] = mapped_column(String(256), nullable=False, comment="机会标题")
    suggested_angle: Mapped[str] = mapped_column(String(256), nullable=False, comment="建议角度")
    target_audience: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="目标人群")
    content_pillar: Mapped[str] = mapped_column(String(64), nullable=False, comment="内容支柱")
    comment_demand_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="评论需求类型")
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False, comment="证据摘要")
    replicability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="可复制性评分")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="风险等级")
    risk_points: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="风险点")
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="机会评分")
    content_goal: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Strategy 为该机会定义的内容目标")
    why_now: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Strategy 中当前执行该机会的依据")
    suggested_hook: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Strategy 建议的内容 Hook")
    evidence_refs: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True, comment="Strategy Opportunity 证据引用")
    constraints: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="Strategy Opportunity 最终合并约束")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
