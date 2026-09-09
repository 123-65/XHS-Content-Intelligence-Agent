from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MCPToolCallLog(Base):
    """MCP 工具调用日志。"""

    __tablename__ = "mcp_tool_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_run.id"), nullable=True, comment="Agent run ID")
    agent_step_id: Mapped[int | None] = mapped_column(ForeignKey("agent_step.id"), nullable=True, comment="Agent step ID")
    server_config_id: Mapped[int | None] = mapped_column(ForeignKey("mcp_server_config.id"), nullable=True, comment="Server config ID")
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Tool name")
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="Call status")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Tool input")
    output_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Tool output")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Error message")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Latency milliseconds")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    requires_confirmation: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Requires confirmation")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
