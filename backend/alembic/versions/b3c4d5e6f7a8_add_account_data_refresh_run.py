"""add account data refresh run

Revision ID: b3c4d5e6f7a8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_data_refresh_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("data_source_config_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("refresh_scope_days", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["data_source_config_id"], ["account_data_source_config.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_account_data_refresh_run_account_id"), "account_data_refresh_run", ["account_id"], unique=False)
    op.create_index(
        op.f("ix_account_data_refresh_run_data_source_config_id"),
        "account_data_refresh_run",
        ["data_source_config_id"],
        unique=False,
    )
    op.create_index(op.f("ix_account_data_refresh_run_id"), "account_data_refresh_run", ["id"], unique=False)
    op.create_index(op.f("ix_account_data_refresh_run_status"), "account_data_refresh_run", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_account_data_refresh_run_status"), table_name="account_data_refresh_run")
    op.drop_index(op.f("ix_account_data_refresh_run_id"), table_name="account_data_refresh_run")
    op.drop_index(op.f("ix_account_data_refresh_run_data_source_config_id"), table_name="account_data_refresh_run")
    op.drop_index(op.f("ix_account_data_refresh_run_account_id"), table_name="account_data_refresh_run")
    op.drop_table("account_data_refresh_run")
