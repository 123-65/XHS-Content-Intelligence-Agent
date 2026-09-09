from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContextSnapshot(Base):
    """Actual context injected for one LLM call."""

    __tablename__ = "context_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_run.id"), nullable=True, index=True, comment="Agent run ID")
    agent_step_id: Mapped[int | None] = mapped_column(ForeignKey("agent_step.id"), nullable=True, index=True, comment="Agent step ID")
    prompt_run_log_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_run_log.id"), nullable=True, index=True, comment="Prompt run log ID")
    task_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="Context task name")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="LLM model")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="LLM provider")
    token_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Token budget")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Injected token estimate")
    system_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="System prompt tokens")
    user_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="User prompt tokens")
    memory_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Memory slots used")
    memory_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Memory tokens")
    slot_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Slot count")
    truncated: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Was any context truncated")
    injected_slot_names: Mapped[list] = mapped_column(JSONB, default=list, nullable=False, comment="Injected slots")
    slot_token_breakdown: Mapped[list] = mapped_column(JSONB, default=list, nullable=False, comment="Slot token ratios")
    truncation_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Truncation details")
    sanitizer_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Sanitizer details")
    memory_usage_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Memory usage details")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="Hash of final injected prompt")
    prompt_preview: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Governed prompt preview")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    slot_logs: Mapped[list["ContextSlotLog"]] = relationship("ContextSlotLog", back_populates="snapshot")

