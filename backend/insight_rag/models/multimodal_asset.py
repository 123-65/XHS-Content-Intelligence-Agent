from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from insight_rag.core.db import Base


class MultimodalAsset(Base):
    __tablename__ = "multimodal_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(40), default="image", index=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), default=None)
    content_type: Mapped[str | None] = mapped_column(String(120), default=None)
    bucket: Mapped[str] = mapped_column(String(120))
    object_key: Mapped[str] = mapped_column(String(600), index=True)
    public_url: Mapped[str] = mapped_column(String(1000))
    image_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    image_index: Mapped[int | None] = mapped_column(Integer, default=None)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    file_size: Mapped[int | None] = mapped_column(Integer, default=None)
    ocr_text: Mapped[str | None] = mapped_column(Text, default=None)
    image_caption: Mapped[str | None] = mapped_column(Text, default=None)
    caption_chunk_id: Mapped[int | None] = mapped_column(Integer, default=None)
    ocr_chunk_id: Mapped[int | None] = mapped_column(Integer, default=None)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

