from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategyMemory(Base):
    """从发布后复盘中提取的策略记忆。"""

    __tablename__ = "strategy_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="Account ID")
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Memory type")
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", nullable=False, comment="Memory status")
    summary: Mapped[str] = mapped_column(Text, nullable=False, comment="Memory summary")
    pattern: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Reusable pattern")
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    source_review_report_id: Mapped[int | None] = mapped_column(ForeignKey("review_report.id"), nullable=True, comment="Source review report ID")
    support_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False, comment="Risk level")
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Metadata payload")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
