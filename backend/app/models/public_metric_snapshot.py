from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PublicMetricSnapshot(Base):
    """已发布笔记的公开指标快照。"""

    __tablename__ = "public_metric_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    published_note_id: Mapped[int] = mapped_column(ForeignKey("published_note.id"), nullable=False, comment="Published note ID")
    snapshot_window: Mapped[str] = mapped_column(String(16), nullable=False, comment="Snapshot window")
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    collect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    share_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    follow_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profile_visit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False, comment="Source type")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Raw metric snapshot")
