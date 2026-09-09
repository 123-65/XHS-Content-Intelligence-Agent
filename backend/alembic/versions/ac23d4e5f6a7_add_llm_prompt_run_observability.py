"""add llm prompt run observability

Revision ID: ac23d4e5f6a7
Revises: ab12c3d4e5f6
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ac23d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "ab12c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add LLM observability fields to prompt_run_log."""
    op.add_column("prompt_run_log", sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Governed input summary"))
    op.add_column("prompt_run_log", sa.Column("output_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Governed output summary"))
    op.add_column("prompt_run_log", sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False, comment="LLM latency milliseconds"))
    op.add_column("prompt_run_log", sa.Column("fallback_used", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="Fallback used"))
    op.add_column("prompt_run_log", sa.Column("fallback_from", sa.String(length=64), nullable=True, comment="Fallback source provider"))


def downgrade() -> None:
    """Drop LLM observability fields from prompt_run_log."""
    op.drop_column("prompt_run_log", "fallback_from")
    op.drop_column("prompt_run_log", "fallback_used")
    op.drop_column("prompt_run_log", "latency_ms")
    op.drop_column("prompt_run_log", "output_summary")
    op.drop_column("prompt_run_log", "input_summary")

