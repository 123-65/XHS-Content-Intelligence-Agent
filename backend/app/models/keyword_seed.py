from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KeywordSeed(Base):
    """关键词种子表。"""

    __tablename__ = "keyword_seed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="账号 ID")
    keyword: Mapped[str] = mapped_column(String(128), nullable=False, comment="关键词")
    category: Mapped[str] = mapped_column(String(64), nullable=False, comment="关键词分类")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="生成理由")
    source_type: Mapped[str] = mapped_column(String(32), default="RULE_TEMPLATE", nullable=False, comment="来源类型")
    confidence: Mapped[float] = mapped_column(default=0.8, nullable=False, comment="置信度")
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="原始生成快照")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, comment="采集/生成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
