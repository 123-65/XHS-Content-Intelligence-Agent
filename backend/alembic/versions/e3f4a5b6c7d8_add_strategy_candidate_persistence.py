"""add strategy candidate persistence

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-09-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建具有稳定数据库标识的发布后复盘策略候选。"""
    op.create_table(
        "strategy_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_report_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("source_candidate_index", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("supporting_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contradicting_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PROPOSED", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'CONFIRMED', 'REJECTED')",
            name="ck_strategy_candidate_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["review_report_id"], ["review_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_candidate_account_id", "strategy_candidate", ["account_id"])
    op.create_index("ix_strategy_candidate_review_report_id", "strategy_candidate", ["review_report_id"])
    op.create_index("ix_strategy_candidate_status", "strategy_candidate", ["status"])
    op.create_index(
        "ix_strategy_candidate_review_source",
        "strategy_candidate",
        ["review_report_id", "source_candidate_index"],
    )


def downgrade() -> None:
    """删除策略候选专用表，不修改 Review 快照。"""
    op.drop_index("ix_strategy_candidate_review_source", table_name="strategy_candidate")
    op.drop_index("ix_strategy_candidate_status", table_name="strategy_candidate")
    op.drop_index("ix_strategy_candidate_review_report_id", table_name="strategy_candidate")
    op.drop_index("ix_strategy_candidate_account_id", table_name="strategy_candidate")
    op.drop_table("strategy_candidate")
