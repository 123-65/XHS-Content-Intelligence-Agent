"""add account evidence refresh run

Revision ID: b4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_evidence_refresh_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("data_refresh_run_id", sa.Integer(), nullable=True),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("keyword", sa.String(length=128), nullable=True),
        sa.Column("target_metric", sa.String(length=32), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["data_refresh_run_id"], ["account_data_refresh_run.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["competitor_analysis_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_account_evidence_refresh_run_account_id"), "account_evidence_refresh_run", ["account_id"], unique=False)
    op.create_index(
        op.f("ix_account_evidence_refresh_run_data_refresh_run_id"),
        "account_evidence_refresh_run",
        ["data_refresh_run_id"],
        unique=False,
    )
    op.create_index(op.f("ix_account_evidence_refresh_run_id"), "account_evidence_refresh_run", ["id"], unique=False)
    op.create_index(op.f("ix_account_evidence_refresh_run_report_id"), "account_evidence_refresh_run", ["report_id"], unique=False)
    op.create_index(op.f("ix_account_evidence_refresh_run_status"), "account_evidence_refresh_run", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_account_evidence_refresh_run_status"), table_name="account_evidence_refresh_run")
    op.drop_index(op.f("ix_account_evidence_refresh_run_report_id"), table_name="account_evidence_refresh_run")
    op.drop_index(op.f("ix_account_evidence_refresh_run_id"), table_name="account_evidence_refresh_run")
    op.drop_index(op.f("ix_account_evidence_refresh_run_data_refresh_run_id"), table_name="account_evidence_refresh_run")
    op.drop_index(op.f("ix_account_evidence_refresh_run_account_id"), table_name="account_evidence_refresh_run")
    op.drop_table("account_evidence_refresh_run")
