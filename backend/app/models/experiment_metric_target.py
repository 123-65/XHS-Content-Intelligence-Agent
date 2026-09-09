from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExperimentMetricTarget(Base):
    """实验指标目标表。"""

    __tablename__ = "experiment_metric_target"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("content_experiment.id"), nullable=False, comment="内容实验 ID")
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="指标名称")
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="指标类型")
    target_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False, comment="目标值")
    comparison_operator: Mapped[str] = mapped_column(String(16), default=">=", nullable=False, comment="比较符")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="指标说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
