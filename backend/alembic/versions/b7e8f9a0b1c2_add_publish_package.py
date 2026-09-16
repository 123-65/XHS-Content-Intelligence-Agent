"""add publish package

Revision ID: b7e8f9a0b1c2
Revises: b6d7e8f9a0b1
Create Date: 2026-09-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "b6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publish_package",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("review_report_id", sa.Integer(), nullable=True),
        sa.Column("revision_plan_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cta", sa.Text(), nullable=True),
        sa.Column("cover_card", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("image_cards", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("publish_checklist", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manual_publish_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["content_draft.id"]),
        sa.ForeignKeyConstraint(["review_report_id"], ["review_report.id"]),
        sa.ForeignKeyConstraint(["revision_plan_id"], ["draft_revision_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_publish_package_account_id"), "publish_package", ["account_id"], unique=False)
    op.create_index(op.f("ix_publish_package_draft_id"), "publish_package", ["draft_id"], unique=False)
    op.create_index(op.f("ix_publish_package_id"), "publish_package", ["id"], unique=False)
    op.create_index(op.f("ix_publish_package_review_report_id"), "publish_package", ["review_report_id"], unique=False)
    op.create_index(op.f("ix_publish_package_revision_plan_id"), "publish_package", ["revision_plan_id"], unique=False)
    op.create_index(op.f("ix_publish_package_source_type"), "publish_package", ["source_type"], unique=False)
    op.create_index(op.f("ix_publish_package_status"), "publish_package", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_publish_package_status"), table_name="publish_package")
    op.drop_index(op.f("ix_publish_package_source_type"), table_name="publish_package")
    op.drop_index(op.f("ix_publish_package_revision_plan_id"), table_name="publish_package")
    op.drop_index(op.f("ix_publish_package_review_report_id"), table_name="publish_package")
    op.drop_index(op.f("ix_publish_package_id"), table_name="publish_package")
    op.drop_index(op.f("ix_publish_package_draft_id"), table_name="publish_package")
    op.drop_index(op.f("ix_publish_package_account_id"), table_name="publish_package")
    op.drop_table("publish_package")
