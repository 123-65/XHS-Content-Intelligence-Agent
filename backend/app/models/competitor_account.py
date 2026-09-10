from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompetitorAccount(Base):
    """同行账号快照表。"""

    __tablename__ = "competitor_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="本系统账号 ID")
    platform: Mapped[str] = mapped_column(String(32), default="xhs", nullable=False, comment="平台")
    platform_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="平台账号 ID")
    nickname: Mapped[str] = mapped_column(String(128), nullable=False, comment="同行账号昵称")
    homepage_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="主页链接")
    bio: Mapped[str | None] = mapped_column(Text, nullable=True, comment="简介")
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="粉丝数")
    note_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="笔记数")
    source_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False, comment="来源类型")
    provider_name: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False, comment="Provider name")
    is_mock: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Is mock data")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, comment="采集时间")
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False, comment="置信度")
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="原始快照")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
