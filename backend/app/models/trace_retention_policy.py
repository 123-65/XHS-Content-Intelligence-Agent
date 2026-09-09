from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TraceRetentionPolicy(Base):
    """Trace log storage, redaction, and retention policy."""

    __tablename__ = "trace_retention_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    log_table: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="Trace table name")
    raw_payload_policy: Mapped[str] = mapped_column(String(64), default="summary_hash_when_long", nullable=False, comment="Raw payload policy")
    max_raw_chars: Mapped[int] = mapped_column(Integer, default=6000, nullable=False, comment="Max chars stored raw")
    summary_chars: Mapped[int] = mapped_column(Integer, default=1200, nullable=False, comment="Summary chars stored after truncation")
    hash_algorithm: Mapped[str] = mapped_column(String(16), default="sha256", nullable=False, comment="Hash algorithm")
    retention_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False, comment="Retention days")
    sensitive_fields: Mapped[list] = mapped_column(JSONB, default=list, nullable=False, comment="Sensitive fields")
    redact_patterns: Mapped[list] = mapped_column(JSONB, default=list, nullable=False, comment="Redaction pattern labels")
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False, comment="Policy enabled")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

