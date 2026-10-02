from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkflowOperation(Base):
    __tablename__ = "workflow_operation"
    __table_args__ = (
        UniqueConstraint("run_ref", "operation_key", name="uq_workflow_operation_run_key"),
        Index("ix_workflow_operation_run_ref", "run_ref"),
        Index("ix_workflow_operation_tool_name", "tool_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_ref: Mapped[str] = mapped_column(ForeignKey("workflow_run.run_ref", ondelete="CASCADE"), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
