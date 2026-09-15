from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountDataSourceConfig(Base):
    """Long-lived data source configuration for one account and platform."""

    __tablename__ = "account_data_source_config"
    __table_args__ = (UniqueConstraint("account_id", "platform", name="uq_account_data_source_config_account_platform"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="xhs", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, index=True)
    keywords: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    competitor_accounts: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    note_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    refresh_policy: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
