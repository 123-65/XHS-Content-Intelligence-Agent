"""add draft revision plan

Revision ID: b6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_revision_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("review_report_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("feedback_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("base_draft_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversation.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["content_draft.id"]),
        sa.ForeignKeyConstraint(["review_report_id"], ["review_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_draft_revision_plan_account_id"), "draft_revision_plan", ["account_id"], unique=False)
    op.create_index(op.f("ix_draft_revision_plan_conversation_id"), "draft_revision_plan", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_draft_revision_plan_draft_id"), "draft_revision_plan", ["draft_id"], unique=False)
    op.create_index(op.f("ix_draft_revision_plan_id"), "draft_revision_plan", ["id"], unique=False)
    op.create_index(op.f("ix_draft_revision_plan_review_report_id"), "draft_revision_plan", ["review_report_id"], unique=False)
    op.create_index(op.f("ix_draft_revision_plan_status"), "draft_revision_plan", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_draft_revision_plan_status"), table_name="draft_revision_plan")
    op.drop_index(op.f("ix_draft_revision_plan_review_report_id"), table_name="draft_revision_plan")
    op.drop_index(op.f("ix_draft_revision_plan_id"), table_name="draft_revision_plan")
    op.drop_index(op.f("ix_draft_revision_plan_draft_id"), table_name="draft_revision_plan")
    op.drop_index(op.f("ix_draft_revision_plan_conversation_id"), table_name="draft_revision_plan")
    op.drop_index(op.f("ix_draft_revision_plan_account_id"), table_name="draft_revision_plan")
    op.drop_table("draft_revision_plan")
