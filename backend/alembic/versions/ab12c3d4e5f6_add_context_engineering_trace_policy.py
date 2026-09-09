"""add context engineering trace policy

Revision ID: ab12c3d4e5f6
Revises: c6e7f8a9b120
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ab12c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c6e7f8a9b120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create context snapshot and trace retention tables."""
    op.create_table(
        "context_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True, comment="Agent run ID"),
        sa.Column("agent_step_id", sa.Integer(), nullable=True, comment="Agent step ID"),
        sa.Column("prompt_run_log_id", sa.Integer(), nullable=True, comment="Prompt run log ID"),
        sa.Column("task_name", sa.String(length=128), nullable=False, comment="Context task name"),
        sa.Column("model", sa.String(length=128), nullable=True, comment="LLM model"),
        sa.Column("provider", sa.String(length=64), nullable=True, comment="LLM provider"),
        sa.Column("token_budget", sa.Integer(), nullable=False, server_default="0", comment="Token budget"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0", comment="Injected token estimate"),
        sa.Column("system_tokens", sa.Integer(), nullable=False, server_default="0", comment="System prompt tokens"),
        sa.Column("user_tokens", sa.Integer(), nullable=False, server_default="0", comment="User prompt tokens"),
        sa.Column("memory_count", sa.Integer(), nullable=False, server_default="0", comment="Memory slots used"),
        sa.Column("memory_tokens", sa.Integer(), nullable=False, server_default="0", comment="Memory tokens"),
        sa.Column("slot_count", sa.Integer(), nullable=False, server_default="0", comment="Slot count"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="Was any context truncated"),
        sa.Column("injected_slot_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb"), comment="Injected slots"),
        sa.Column("slot_token_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb"), comment="Slot token ratios"),
        sa.Column("truncation_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Truncation details"),
        sa.Column("sanitizer_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Sanitizer details"),
        sa.Column("memory_usage_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Memory usage details"),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False, comment="Hash of final injected prompt"),
        sa.Column("prompt_preview", sa.Text(), nullable=True, comment="Governed prompt preview"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"]),
        sa.ForeignKeyConstraint(["agent_step_id"], ["agent_step.id"]),
        sa.ForeignKeyConstraint(["prompt_run_log_id"], ["prompt_run_log.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_context_snapshot_id"), "context_snapshot", ["id"], unique=False)
    op.create_index(op.f("ix_context_snapshot_agent_run_id"), "context_snapshot", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_context_snapshot_agent_step_id"), "context_snapshot", ["agent_step_id"], unique=False)
    op.create_index(op.f("ix_context_snapshot_prompt_run_log_id"), "context_snapshot", ["prompt_run_log_id"], unique=False)
    op.create_index(op.f("ix_context_snapshot_task_name"), "context_snapshot", ["task_name"], unique=False)

    op.create_table(
        "context_slot_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("context_snapshot_id", sa.Integer(), nullable=False, comment="Context snapshot ID"),
        sa.Column("slot_name", sa.String(length=64), nullable=False, comment="Context slot name"),
        sa.Column("role", sa.String(length=16), nullable=False, comment="Prompt role"),
        sa.Column("source_type", sa.String(length=64), nullable=False, comment="Source type"),
        sa.Column("trust_level", sa.String(length=16), nullable=False, comment="Trust level"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50", comment="Budget priority"),
        sa.Column("original_tokens", sa.Integer(), nullable=False, server_default="0", comment="Original token estimate"),
        sa.Column("injected_tokens", sa.Integer(), nullable=False, server_default="0", comment="Injected token estimate"),
        sa.Column("token_ratio", sa.Numeric(10, 6), nullable=False, server_default="0", comment="Share of snapshot tokens"),
        sa.Column("was_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="Was slot truncated"),
        sa.Column("truncation_reason", sa.String(length=64), nullable=True, comment="Truncation reason"),
        sa.Column("content_hash", sa.String(length=64), nullable=True, comment="Original slot content hash"),
        sa.Column("content_preview", sa.Text(), nullable=True, comment="Governed content preview"),
        sa.Column("metadata_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Slot metadata"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["context_snapshot_id"], ["context_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_context_slot_log_id"), "context_slot_log", ["id"], unique=False)
    op.create_index(op.f("ix_context_slot_log_context_snapshot_id"), "context_slot_log", ["context_snapshot_id"], unique=False)
    op.create_index(op.f("ix_context_slot_log_slot_name"), "context_slot_log", ["slot_name"], unique=False)

    op.create_table(
        "trace_retention_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_table", sa.String(length=64), nullable=False, comment="Trace table name"),
        sa.Column("raw_payload_policy", sa.String(length=64), nullable=False, server_default="summary_hash_when_long", comment="Raw payload policy"),
        sa.Column("max_raw_chars", sa.Integer(), nullable=False, server_default="6000", comment="Max chars stored raw"),
        sa.Column("summary_chars", sa.Integer(), nullable=False, server_default="1200", comment="Summary chars stored after truncation"),
        sa.Column("hash_algorithm", sa.String(length=16), nullable=False, server_default="sha256", comment="Hash algorithm"),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="14", comment="Retention days"),
        sa.Column("sensitive_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb"), comment="Sensitive fields"),
        sa.Column("redact_patterns", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb"), comment="Redaction pattern labels"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="Policy enabled"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("log_table"),
    )
    op.create_index(op.f("ix_trace_retention_policy_id"), "trace_retention_policy", ["id"], unique=False)
    op.create_index(op.f("ix_trace_retention_policy_log_table"), "trace_retention_policy", ["log_table"], unique=True)


def downgrade() -> None:
    """Drop context snapshot and trace retention tables."""
    op.drop_index(op.f("ix_trace_retention_policy_log_table"), table_name="trace_retention_policy")
    op.drop_index(op.f("ix_trace_retention_policy_id"), table_name="trace_retention_policy")
    op.drop_table("trace_retention_policy")
    op.drop_index(op.f("ix_context_slot_log_slot_name"), table_name="context_slot_log")
    op.drop_index(op.f("ix_context_slot_log_context_snapshot_id"), table_name="context_slot_log")
    op.drop_index(op.f("ix_context_slot_log_id"), table_name="context_slot_log")
    op.drop_table("context_slot_log")
    op.drop_index(op.f("ix_context_snapshot_task_name"), table_name="context_snapshot")
    op.drop_index(op.f("ix_context_snapshot_prompt_run_log_id"), table_name="context_snapshot")
    op.drop_index(op.f("ix_context_snapshot_agent_step_id"), table_name="context_snapshot")
    op.drop_index(op.f("ix_context_snapshot_agent_run_id"), table_name="context_snapshot")
    op.drop_index(op.f("ix_context_snapshot_id"), table_name="context_snapshot")
    op.drop_table("context_snapshot")

