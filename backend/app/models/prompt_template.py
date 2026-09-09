from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PromptTemplate(Base):
    """Prompt template version table."""

    __tablename__ = "prompt_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prompt_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Prompt name")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, comment="Prompt version")
    template_path: Mapped[str] = mapped_column(String(256), nullable=False, comment="Template path")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="System prompt")
    user_template: Mapped[str] = mapped_column(Text, nullable=False, comment="User prompt template")
    output_schema: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="Output JSON schema")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, comment="Template status")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
