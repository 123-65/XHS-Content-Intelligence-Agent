from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvalCase(Base):
    """Evaluation case table."""

    __tablename__ = "eval_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    suite_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Suite name")
    case_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="Stable case key")
    eval_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Evaluation type")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Input payload")
    expected_output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Expected output")
    case_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False, comment="Case metadata")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Is active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
