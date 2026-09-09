from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NoteCommentSnapshot(Base):
    """已发布笔记的评论快照。"""

    __tablename__ = "note_comment_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    published_note_id: Mapped[int] = mapped_column(ForeignKey("published_note.id"), nullable=False, comment="Published note ID")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Comment content")
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Author name")
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demand_type: Mapped[str] = mapped_column(String(64), default="UNKNOWN", nullable=False, comment="Demand type")
    source_type: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False, comment="Source type")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Raw comment snapshot")
