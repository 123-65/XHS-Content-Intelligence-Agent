from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategyMemoryUsage(Base):
    """Agent 使用策略记忆的记录。"""

    __tablename__ = "strategy_memory_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True, comment="Account ID")
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False, comment="Agent run ID")
    memory_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_memory.id"), nullable=True, comment="Memory ID")
    usage_reason: Mapped[str] = mapped_column(Text, nullable=False, comment="Usage reason")
    usage_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Usage snapshot")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
