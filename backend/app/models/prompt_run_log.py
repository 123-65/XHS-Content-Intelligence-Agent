from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PromptRunLog(Base):
    """Prompt run log table."""

    __tablename__ = "prompt_run_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prompt_template_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_template.id"), nullable=True, comment="Prompt template ID")
    prompt_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Prompt name")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, comment="Prompt version")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Input payload snapshot")
    input_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Governed input summary")
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="Rendered prompt")
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Raw model output")
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Structured output")
    output_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Governed output summary")
    model: Mapped[str] = mapped_column(String(128), nullable=False, comment="Model")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, comment="Provider")
    prompt_key: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Prompt key")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="LLM latency milliseconds")
    is_mock: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Is mock provider")
    fallback_used: Mapped[bool] = mapped_column(default=False, nullable=False, comment="Fallback used")
    fallback_from: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Fallback source provider")
    raw_response_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Raw response ID")
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False, comment="Run status")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Error message")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
