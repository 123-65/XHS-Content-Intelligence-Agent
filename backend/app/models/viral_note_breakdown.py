from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ViralNoteBreakdown(Base):
    """爆款笔记拆解表。"""

    __tablename__ = "viral_note_breakdown"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("competitor_analysis_report.id"), nullable=False, comment="竞品分析报告 ID")
    competitor_note_id: Mapped[int] = mapped_column(ForeignKey("competitor_note.id"), nullable=False, comment="竞品笔记 ID")
    note_title: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="笔记标题")
    note_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="笔记链接")
    engagement_score: Mapped[float] = mapped_column(default=0, nullable=False, comment="互动表现分")
    title_pattern: Mapped[str] = mapped_column(String(64), nullable=False, comment="标题模式")
    cover_pattern: Mapped[str] = mapped_column(String(64), nullable=False, comment="封面模式")
    content_structure: Mapped[str] = mapped_column(String(64), nullable=False, comment="内容结构")
    comment_demands: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="评论需求")
    conversion_signals: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="转化信号")
    replicability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="可复制性评分")
    risk_points: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="风险点")
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False, comment="证据摘要")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
