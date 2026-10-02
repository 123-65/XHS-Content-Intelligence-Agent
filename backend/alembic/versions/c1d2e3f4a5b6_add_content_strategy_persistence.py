"""add content strategy persistence

Revision ID: c1d2e3f4a5b6
Revises: b7e8f9a0b1c2
Create Date: 2026-09-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增专用 Strategy Artifact 表并扩展现有 Opportunity 的派生关系。"""
    op.create_table(
        "content_strategy_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("research_artifact_id", sa.Integer(), nullable=False),
        sa.Column("strategy_goal", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("content_directions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("applicable_constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["research_artifact_id"], ["competitor_analysis_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_strategy_artifact_account_id", "content_strategy_artifact", ["account_id"], unique=False)
    op.create_index("ix_content_strategy_artifact_research_artifact_id", "content_strategy_artifact", ["research_artifact_id"], unique=False)
    op.create_index("ix_content_strategy_artifact_account_created_at", "content_strategy_artifact", ["account_id", "created_at"], unique=False)

    op.add_column("content_opportunity", sa.Column("strategy_artifact_id", sa.Integer(), nullable=True, comment="派生该机会的内容策略 Artifact ID"))
    op.add_column("content_opportunity", sa.Column("source_opportunity_id", sa.Integer(), nullable=True, comment="Strategy Opportunity 对应的 Research Opportunity ID"))
    op.add_column("content_opportunity", sa.Column("content_goal", sa.Text(), nullable=True, comment="Strategy 为该机会定义的内容目标"))
    op.add_column("content_opportunity", sa.Column("why_now", sa.Text(), nullable=True, comment="Strategy 中当前执行该机会的依据"))
    op.add_column("content_opportunity", sa.Column("suggested_hook", sa.Text(), nullable=True, comment="Strategy 建议的内容 Hook"))
    op.add_column("content_opportunity", sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Strategy Opportunity 证据引用"))
    op.add_column("content_opportunity", sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Strategy Opportunity 最终合并约束"))
    op.create_foreign_key("fk_content_opportunity_strategy_artifact_id", "content_opportunity", "content_strategy_artifact", ["strategy_artifact_id"], ["id"])
    op.create_foreign_key("fk_content_opportunity_source_opportunity_id", "content_opportunity", "content_opportunity", ["source_opportunity_id"], ["id"])
    op.create_index("ix_content_opportunity_strategy_artifact_id", "content_opportunity", ["strategy_artifact_id"], unique=False)
    op.create_index("ix_content_opportunity_source_opportunity_id", "content_opportunity", ["source_opportunity_id"], unique=False)
    op.create_index("ix_content_opportunity_report_id", "content_opportunity", ["report_id"], unique=False)
    op.create_check_constraint(
        "ck_content_opportunity_strategy_fields_complete",
        "content_opportunity",
        "strategy_artifact_id IS NULL OR (source_opportunity_id IS NOT NULL AND content_goal IS NOT NULL AND why_now IS NOT NULL AND suggested_hook IS NOT NULL AND evidence_refs IS NOT NULL AND constraints IS NOT NULL)",
    )


def downgrade() -> None:
    """只回滚本阶段新增的 Strategy 表、约束、索引与字段。"""
    op.drop_constraint("ck_content_opportunity_strategy_fields_complete", "content_opportunity", type_="check")
    op.drop_index("ix_content_opportunity_report_id", table_name="content_opportunity")
    op.drop_index("ix_content_opportunity_source_opportunity_id", table_name="content_opportunity")
    op.drop_index("ix_content_opportunity_strategy_artifact_id", table_name="content_opportunity")
    op.drop_constraint("fk_content_opportunity_source_opportunity_id", "content_opportunity", type_="foreignkey")
    op.drop_constraint("fk_content_opportunity_strategy_artifact_id", "content_opportunity", type_="foreignkey")
    op.drop_column("content_opportunity", "constraints")
    op.drop_column("content_opportunity", "evidence_refs")
    op.drop_column("content_opportunity", "suggested_hook")
    op.drop_column("content_opportunity", "why_now")
    op.drop_column("content_opportunity", "content_goal")
    op.drop_column("content_opportunity", "source_opportunity_id")
    op.drop_column("content_opportunity", "strategy_artifact_id")
    op.drop_index("ix_content_strategy_artifact_account_created_at", table_name="content_strategy_artifact")
    op.drop_index("ix_content_strategy_artifact_research_artifact_id", table_name="content_strategy_artifact")
    op.drop_index("ix_content_strategy_artifact_account_id", table_name="content_strategy_artifact")
    op.drop_table("content_strategy_artifact")
