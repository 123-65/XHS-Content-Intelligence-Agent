from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompetitorAnalysisReport(Base):
    """竞品内容分析报告表。"""

    __tablename__ = "competitor_analysis_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account_profile.id"), nullable=True, comment="关联账号 ID")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="分析报告名称")
    keyword: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="分析关键词")
    source_type: Mapped[str] = mapped_column(String(32), default="COMPETITOR", nullable=False, comment="分析数据来源")
    target_metric: Mapped[str] = mapped_column(String(32), default="engagement", nullable=False, comment="目标指标")
    note_snapshot_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False, comment="参与分析的笔记快照 ID")
    competitor_account_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False, comment="参与分析的同行账号 ID")
    competitor_note_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False, comment="参与分析的竞品笔记 ID")
    note_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="参与分析的笔记数量")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="参与分析的评论数量")
    persona_patterns: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="同行账号人设")
    content_pillars: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="内容支柱")
    top_tags: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="高频标签")
    title_patterns: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="标题模式")
    cover_patterns: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="封面模式")
    content_structures: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="内容结构")
    comment_demands: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="评论需求")
    conversion_signals: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="转化信号")
    replicability_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="可复制性总结")
    risk_points: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="风险点")
    high_performance_notes: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="高表现笔记")
    content_insights: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="内容洞察")
    suggestions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="创作建议")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="分析摘要")
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False, comment="分析状态")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
