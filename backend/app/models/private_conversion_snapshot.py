from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PrivateConversionSnapshot(Base):
    """用户人工录入的私域转化快照。"""

    __tablename__ = "private_conversion_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="Account ID")
    published_note_id: Mapped[int] = mapped_column(ForeignKey("published_note.id"), nullable=False, comment="Published note ID")
    snapshot_window: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="Snapshot window")
    dm_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lead_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wechat_add_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    group_join_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consultation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_inquiry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resource_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False, comment="Source type")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Raw conversion snapshot")
