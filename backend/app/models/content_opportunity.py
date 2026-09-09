from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentOpportunity(Base):
    """内容机会表。"""

    __tablename__ = "content_opportunity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("competitor_analysis_report.id"), nullable=False, comment="竞品分析报告 ID")
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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
