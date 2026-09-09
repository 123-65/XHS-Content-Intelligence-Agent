from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MCPServerConfig(Base):
    """MCP Server 接入配置。"""

    __tablename__ = "mcp_server_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, comment="Server name")
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="Base URL")
    status: Mapped[str] = mapped_column(String(32), default="MOCK", nullable=False, comment="Server status")
    auth_type: Mapped[str] = mapped_column(String(32), default="NONE", nullable=False, comment="Auth type")
    allowed_tools: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="Allowed tools")
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    requires_confirmation: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Requires confirmation")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Description")
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Metadata payload")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
