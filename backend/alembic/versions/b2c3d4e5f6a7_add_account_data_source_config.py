"""add account data source config

Revision ID: b2c3d4e5f6a7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_data_source_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("competitor_accounts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("note_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("refresh_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "platform", name="uq_account_data_source_config_account_platform"),
    )
    op.create_index(op.f("ix_account_data_source_config_account_id"), "account_data_source_config", ["account_id"], unique=False)
    op.create_index(op.f("ix_account_data_source_config_id"), "account_data_source_config", ["id"], unique=False)
    op.create_index(op.f("ix_account_data_source_config_platform"), "account_data_source_config", ["platform"], unique=False)
    op.create_index(op.f("ix_account_data_source_config_status"), "account_data_source_config", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_account_data_source_config_status"), table_name="account_data_source_config")
    op.drop_index(op.f("ix_account_data_source_config_platform"), table_name="account_data_source_config")
    op.drop_index(op.f("ix_account_data_source_config_id"), table_name="account_data_source_config")
    op.drop_index(op.f("ix_account_data_source_config_account_id"), table_name="account_data_source_config")
    op.drop_table("account_data_source_config")
