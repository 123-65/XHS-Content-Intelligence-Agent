"""add confirmation tables

Revision ID: e9a1f63bd842
Revises: d7e8c3a9f120
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e9a1f63bd842"
down_revision: Union[str, Sequence[str], None] = "d7e8c3a9f120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "confirmation_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("confirmation_type", sa.String(length=64), nullable=False, comment="Confirmation type"),
        sa.Column("target_type", sa.String(length=64), nullable=False, comment="Target type"),
        sa.Column("target_id", sa.Integer(), nullable=False, comment="Target ID"),
        sa.Column("target_version", sa.Integer(), nullable=True, comment="Target version"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Task status"),
        sa.Column("summary", sa.Text(), nullable=False, comment="Task summary"),
        sa.Column("recommendation", sa.Text(), nullable=False, comment="System recommendation"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="Risk level"),
        sa.Column("risk_reason", sa.Text(), nullable=True, comment="Risk reason"),
        sa.Column("payload_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Target payload snapshot"),
        sa.Column("invalidated_reason", sa.Text(), nullable=True, comment="Invalidated reason"),
        sa.Column("created_by", sa.String(length=128), nullable=True, comment="Creator"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_confirmation_task_id"), "confirmation_task", ["id"], unique=False)
    op.create_index("ix_confirmation_task_pending_account", "confirmation_task", ["status", "account_id"], unique=False)
    op.create_index("ix_confirmation_task_target", "confirmation_task", ["target_type", "target_id"], unique=False)

    op.create_table(
        "confirmation_decision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False, comment="Task ID"),
        sa.Column("decision", sa.String(length=32), nullable=False, comment="Decision"),
        sa.Column("decided_by", sa.String(length=128), nullable=True, comment="Decision maker"),
        sa.Column("comment", sa.Text(), nullable=True, comment="Decision comment"),
        sa.Column("revision_request", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Revision request"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["confirmation_task.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_confirmation_decision_id"), "confirmation_decision", ["id"], unique=False)
    op.create_index("ix_confirmation_decision_task", "confirmation_decision", ["task_id"], unique=False)

    op.create_table(
        "confirmation_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False, comment="Task ID"),
        sa.Column("event_type", sa.String(length=64), nullable=False, comment="Audit event type"),
        sa.Column("from_status", sa.String(length=32), nullable=True, comment="Previous status"),
        sa.Column("to_status", sa.String(length=32), nullable=False, comment="Next status"),
        sa.Column("actor", sa.String(length=128), nullable=True, comment="Actor"),
        sa.Column("reason", sa.Text(), nullable=True, comment="Reason"),
        sa.Column("metadata_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Metadata payload"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["confirmation_task.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_confirmation_audit_log_id"), "confirmation_audit_log", ["id"], unique=False)
    op.create_index("ix_confirmation_audit_log_task", "confirmation_audit_log", ["task_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_confirmation_audit_log_task", table_name="confirmation_audit_log")
    op.drop_index(op.f("ix_confirmation_audit_log_id"), table_name="confirmation_audit_log")
    op.drop_table("confirmation_audit_log")
    op.drop_index("ix_confirmation_decision_task", table_name="confirmation_decision")
    op.drop_index(op.f("ix_confirmation_decision_id"), table_name="confirmation_decision")
    op.drop_table("confirmation_decision")
    op.drop_index("ix_confirmation_task_target", table_name="confirmation_task")
    op.drop_index("ix_confirmation_task_pending_account", table_name="confirmation_task")
    op.drop_index(op.f("ix_confirmation_task_id"), table_name="confirmation_task")
    op.drop_table("confirmation_task")
