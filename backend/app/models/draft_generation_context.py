from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DraftGenerationContext(Base):
    """Draft generation context snapshot table."""

    __tablename__ = "draft_generation_context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("content_draft.id"), nullable=True, comment="Draft ID")
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="Account ID")
    experiment_id: Mapped[int] = mapped_column(ForeignKey("content_experiment.id"), nullable=False, comment="Experiment ID")
    content_opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("content_opportunity.id"), nullable=True, comment="Opportunity ID")
    account_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Account snapshot")
    experiment_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Experiment snapshot")
    opportunity_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Opportunity snapshot")
    strategy_memory_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Strategy memory snapshot")
    risk_constraints: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Risk constraints")
    user_requirement: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="User requirement")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
