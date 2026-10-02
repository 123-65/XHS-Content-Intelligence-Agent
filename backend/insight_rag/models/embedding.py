from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from insight_rag.core.db import Base


class EmbeddingRecord(Base):
    __tablename__ = "embedding_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), index=True)
    milvus_collection: Mapped[str] = mapped_column(String(120), index=True)
    milvus_vector_id: Mapped[str] = mapped_column(String(120), index=True)
    embedding_model: Mapped[str] = mapped_column(String(120))
    embedding_dim: Mapped[int] = mapped_column(Integer)
    embedding_hash: Mapped[str] = mapped_column(String(128), index=True)
    embedding_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

