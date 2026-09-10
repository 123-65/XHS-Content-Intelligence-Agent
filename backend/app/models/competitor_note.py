from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompetitorNote(Base):
    """竞品笔记快照表。"""

    __tablename__ = "competitor_note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="本系统账号 ID")
    competitor_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitor_account.id"),
        nullable=True,
        comment="同行账号快照 ID",
    )
    note_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="平台笔记 ID")
    note_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="笔记链接")
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="作者昵称")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="标题")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="正文")
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="标签列表")
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="点赞数")
    collect_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="收藏数")
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="评论数")
    source_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False, comment="来源类型")
    provider_name: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False, comment="Provider name")
    is_mock: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Is mock data")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, comment="采集时间")
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False, comment="置信度")
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="原始快照")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
