from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExperimentVariable(Base):
    """实验变量表。"""

    __tablename__ = "experiment_variable"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("content_experiment.id"), nullable=False, comment="内容实验 ID")
    variable_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="变量名称")
    variable_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="变量类型")
    variable_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="变量取值")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="变量说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
