from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class XhsNoteSnapshot(Base):
    """小红书公开笔记采集快照表。"""

    __tablename__ = "xhs_note_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account_profile.id"), nullable=True, comment="关联账号 ID，可为空")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="数据来源类型")
    keyword: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="采集关键词")
    note_url: Mapped[str] = mapped_column(String(1024), nullable=False, index=True, comment="笔记 URL")
    note_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="笔记 ID")
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="作者名称")
    author_homepage: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="作者主页")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="笔记标题")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="笔记正文")
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="标签列表")
    content_type: Mapped[str] = mapped_column(String(32), default="IMAGE_TEXT", nullable=False, comment="笔记内容类型")
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="封面图 URL")
    image_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False, comment="图片 URL 列表")
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="图片数量")
    image_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="图片 OCR 合并文本")
    image_ocr_items: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False, comment="逐图 OCR 结果")
    merged_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用于分析的合并文本")
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="公开点赞数")
    collect_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="公开收藏数")
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="公开评论数")
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布时间")
    crawl_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, comment="采集时间")
    raw_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="原始内容哈希")
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False, comment="采集状态")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)