from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentExperiment(Base):
    """内容实验表。"""

    __tablename__ = "content_experiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="账号 ID")
    analysis_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitor_analysis_report.id"),
        nullable=True,
        comment="关联竞品分析报告 ID",
    )
    content_opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_opportunity.id"),
        nullable=True,
        comment="关联内容机会 ID",
    )
    experiment_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="实验名称")
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, comment="实验假设")
    content_pillar: Mapped[str] = mapped_column(String(64), default="未分类", nullable=False, comment="内容支柱")
    content_format: Mapped[str] = mapped_column(String(64), default="图文笔记", nullable=False, comment="内容形式")
    main_variable: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="主变量")
    control_variables: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="控制变量")
    primary_metric: Mapped[str] = mapped_column(String(64), default="collect", nullable=False, comment="主指标")
    secondary_metrics: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="辅助指标")
    success_criteria: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="成功标准")
    failure_criteria: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="失败标准")
    fallback_strategy: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败兜底策略")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="风险等级")
    target_metric: Mapped[str] = mapped_column(String(32), nullable=False, comment="目标指标")
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True, comment="预期结果")
    topic_angle: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="选题角度")
    selected_topic: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="最终选题")
    target_values: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="目标数值")
    source_type: Mapped[str] = mapped_column(
        String(32),
        default="COMPETITOR_ANALYSIS",
        nullable=False,
        comment="实验来源",
    )
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False, comment="实验状态")
    publish_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="发布后的笔记链接")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
