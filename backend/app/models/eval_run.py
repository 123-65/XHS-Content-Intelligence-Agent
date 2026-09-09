from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvalRun(Base):
    """Evaluation run result table."""

    __tablename__ = "eval_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    eval_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Evaluation type")
    dataset_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="Dataset path")
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False, comment="Run status")
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pass_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    failed_reasons: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="Failed reasons")
    report_path: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Report path")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
