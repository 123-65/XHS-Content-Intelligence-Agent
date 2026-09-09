from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MCPToolBinding(Base):
    """MCP 工具白名单绑定配置。"""

    __tablename__ = "mcp_tool_binding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_config_id: Mapped[int | None] = mapped_column(ForeignKey("mcp_server_config.id"), nullable=True, comment="Server config ID")
    tool_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, comment="Tool name")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Display name")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Description")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    requires_confirmation: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Requires confirmation")
    fallback_tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Fallback tool name")
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False, comment="Enabled")
    whitelist_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Whitelist rules")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
