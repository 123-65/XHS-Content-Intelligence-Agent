from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from insight_rag.core.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_text: Mapped[str | None] = mapped_column(Text, default=None)
    chunk_hash: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    heading_path: Mapped[str | None] = mapped_column(String(500), default=None)
    sheet_name: Mapped[str | None] = mapped_column(String(255), default=None)
    row_start: Mapped[int | None] = mapped_column(Integer, default=None)
    row_end: Mapped[int | None] = mapped_column(Integer, default=None)
    source_type: Mapped[str | None] = mapped_column(String(40), default="text")
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    embedded: Mapped[bool] = mapped_column(default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", back_populates="chunks")

