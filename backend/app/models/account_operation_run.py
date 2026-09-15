from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountOperationRun(Base):
    """Account-scoped readonly operation analysis run record."""

    __tablename__ = "account_operation_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    data_refresh_run_id: Mapped[int | None] = mapped_column(ForeignKey("account_data_refresh_run.id"), nullable=True, index=True)
    evidence_refresh_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_evidence_refresh_run.id"),
        nullable=True,
        index=True,
    )
    report_id: Mapped[int | None] = mapped_column(ForeignKey("competitor_analysis_report.id"), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    data_gaps: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    next_actions: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
