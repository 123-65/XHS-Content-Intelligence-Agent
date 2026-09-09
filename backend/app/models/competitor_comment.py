from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompetitorComment(Base):
    """竞品评论样本表。"""

    __tablename__ = "competitor_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="本系统账号 ID")
    competitor_note_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitor_note.id"),
        nullable=True,
        comment="竞品笔记快照 ID",
    )
    comment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="平台评论 ID")
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="评论用户")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="评论点赞数")
    source_type: Mapped[str] = mapped_column(String(32), default="SEED_SAMPLE", nullable=False, comment="来源类型")
    provider_name: Mapped[str] = mapped_column(String(64), default="seed_sample", nullable=False, comment="Provider name")
    is_mock: Mapped[bool] = mapped_column(default=True, nullable=False, comment="Is mock data")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, comment="采集时间")
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False, comment="置信度")
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="原始快照")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
