from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkflowRun(Base):
    """五条正式 Workflow 共用的持久化运行与 checkpoint 聚合。"""

    __tablename__ = "workflow_run"
    __table_args__ = (
        CheckConstraint(
            "workflow_name IN ('RESEARCH_V1','CONTENT_STRATEGY_V1','CONTENT_CREATION_V1','CONTENT_REFINEMENT_V1','POST_PUBLISH_REVIEW_V1')",
            name="ck_workflow_run_name",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','WAITING_USER','SUCCESS','PARTIAL_SUCCESS','FAILED','CANCELLED')",
            name="ck_workflow_run_status",
        ),
        CheckConstraint("checkpoint_version >= 1", name="ck_workflow_run_checkpoint_version"),
        UniqueConstraint("run_ref", name="uq_workflow_run_run_ref"),
        Index("ix_workflow_run_workflow_name", "workflow_name"),
        Index("ix_workflow_run_status", "status"),
        Index("ix_workflow_run_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pending_interaction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    checkpoint_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
