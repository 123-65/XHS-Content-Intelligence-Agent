from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRun(Base):
    """Agent 一次工作流运行记录。"""

    __tablename__ = "agent_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="Account ID")
    agent_type: Mapped[str] = mapped_column(String(64), default="WORKFLOW_AGENT", nullable=False, comment="Agent type")
    workflow_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Workflow name")
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False, comment="Run status")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Run input")
    output_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Run output")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Error message")
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Stop reason")
    max_steps: Mapped[int] = mapped_column(Integer, default=8, nullable=False, comment="Max steps")
    max_retry: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="Max retry")
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Token count")
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False, comment="Estimated cost")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Consecutive failures")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
