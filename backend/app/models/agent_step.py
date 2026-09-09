from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentStep(Base):
    """Agent 工作流中的单步工具调用记录。"""

    __tablename__ = "agent_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False, index=True, comment="Agent run ID")
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="Step index")
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Tool name")
    tool_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="Tool type")
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False, comment="Step status")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Tool input")
    output_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Tool output")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Error message")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Retry count")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    requires_confirmation: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Requires confirmation")
    fallback_tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Fallback tool name")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Duration milliseconds")
