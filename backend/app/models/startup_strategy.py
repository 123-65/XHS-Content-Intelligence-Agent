from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StartupStrategy(Base):
    """起号策略表。"""

    __tablename__ = "startup_strategy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="账号 ID")
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="策略名称")
    persona_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True, comment="人设假设")
    content_mix: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="内容组合")
    success_criteria: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="成功标准")
    adjustment_rules: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="调整规则")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, comment="策略状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
