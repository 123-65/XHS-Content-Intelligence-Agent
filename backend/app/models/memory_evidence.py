from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MemoryEvidence(Base):
    """支撑策略记忆的证据明细。"""

    __tablename__ = "memory_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    memory_id: Mapped[int] = mapped_column(ForeignKey("strategy_memory.id"), nullable=False, comment="Memory ID")
    review_report_id: Mapped[int] = mapped_column(ForeignKey("review_report.id"), nullable=False, comment="Review report ID")
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="FACT, INFERENCE, or SUGGESTION")
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False, comment="Evidence text")
    evidence_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Evidence payload")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
