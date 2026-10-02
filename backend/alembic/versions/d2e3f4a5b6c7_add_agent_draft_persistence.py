"""add agent draft persistence

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """在不重写历史 Version 的前提下增加 New Agent Draft Root 与 Version 能力。"""
    op.add_column("content_draft", sa.Column("account_id", sa.Integer(), nullable=True, comment="Draft 所属账号 ID"))
    op.execute(
        "UPDATE content_draft AS draft SET account_id = experiment.account_id "
        "FROM content_experiment AS experiment WHERE draft.experiment_id = experiment.id"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM content_draft WHERE account_id IS NULL) "
        "THEN RAISE EXCEPTION 'content_draft.account_id backfill incomplete'; END IF; END $$"
    )
    op.alter_column("content_draft", "account_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("content_draft", "experiment_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("content_draft", sa.Column("strategy_artifact_id", sa.Integer(), nullable=True, comment="New Agent Strategy Artifact ID"))
    op.add_column("content_draft", sa.Column("opportunity_id", sa.Integer(), nullable=True, comment="New Agent Content Opportunity ID"))
    op.add_column("content_draft", sa.Column("content_goal", sa.Text(), nullable=True, comment="New Agent Draft 不可变内容目标"))
    op.create_foreign_key("fk_content_draft_account_id", "content_draft", "account_profile", ["account_id"], ["id"])
    op.create_foreign_key("fk_content_draft_strategy_artifact_id", "content_draft", "content_strategy_artifact", ["strategy_artifact_id"], ["id"])
    op.create_foreign_key("fk_content_draft_opportunity_id", "content_draft", "content_opportunity", ["opportunity_id"], ["id"])
    op.create_index("ix_content_draft_account_id", "content_draft", ["account_id"], unique=False)
    op.create_index("ix_content_draft_strategy_artifact_id", "content_draft", ["strategy_artifact_id"], unique=False)
    op.create_index("ix_content_draft_opportunity_id", "content_draft", ["opportunity_id"], unique=False)
    op.create_check_constraint(
        "ck_content_draft_agent_identity_complete",
        "content_draft",
        "experiment_id IS NOT NULL OR (account_id IS NOT NULL AND strategy_artifact_id IS NOT NULL AND opportunity_id IS NOT NULL AND content_goal IS NOT NULL)",
    )

    op.add_column("content_draft_version", sa.Column("parent_version_id", sa.Integer(), nullable=True, comment="Previous Draft Version ID"))
    op.add_column("content_draft_version", sa.Column("created_from", sa.String(length=32), nullable=True, comment="New Agent Version 创建来源"))
    op.create_foreign_key("fk_content_draft_version_parent_version_id", "content_draft_version", "content_draft_version", ["parent_version_id"], ["id"])
    op.create_index("ix_content_draft_version_draft_id", "content_draft_version", ["draft_id"], unique=False)
    op.create_index("ix_content_draft_version_parent_version_id", "content_draft_version", ["parent_version_id"], unique=False)
    op.create_index("ix_content_draft_version_draft_version", "content_draft_version", ["draft_id", "version"], unique=False)
    op.create_check_constraint(
        "ck_content_draft_version_created_from",
        "content_draft_version",
        "created_from IS NULL OR created_from IN ('GENERATED', 'REVIEW_REVISION', 'USER_REVISION')",
    )
    op.create_index(
        "uq_content_draft_version_agent_draft_version",
        "content_draft_version",
        ["draft_id", "version"],
        unique=True,
        postgresql_where=sa.text("created_from IS NOT NULL"),
    )


def downgrade() -> None:
    """在不伪造 Experiment 的前提下回滚；存在 New Agent Draft 时明确失败。"""
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM content_draft WHERE experiment_id IS NULL) "
        "THEN RAISE EXCEPTION 'cannot downgrade while New Agent Draft rows exist'; END IF; END $$"
    )
    op.drop_index("uq_content_draft_version_agent_draft_version", table_name="content_draft_version")
    op.drop_constraint("ck_content_draft_version_created_from", "content_draft_version", type_="check")
    op.drop_index("ix_content_draft_version_draft_version", table_name="content_draft_version")
    op.drop_index("ix_content_draft_version_parent_version_id", table_name="content_draft_version")
    op.drop_index("ix_content_draft_version_draft_id", table_name="content_draft_version")
    op.drop_constraint("fk_content_draft_version_parent_version_id", "content_draft_version", type_="foreignkey")
    op.drop_column("content_draft_version", "created_from")
    op.drop_column("content_draft_version", "parent_version_id")

    op.drop_constraint("ck_content_draft_agent_identity_complete", "content_draft", type_="check")
    op.drop_index("ix_content_draft_opportunity_id", table_name="content_draft")
    op.drop_index("ix_content_draft_strategy_artifact_id", table_name="content_draft")
    op.drop_index("ix_content_draft_account_id", table_name="content_draft")
    op.drop_constraint("fk_content_draft_opportunity_id", "content_draft", type_="foreignkey")
    op.drop_constraint("fk_content_draft_strategy_artifact_id", "content_draft", type_="foreignkey")
    op.drop_constraint("fk_content_draft_account_id", "content_draft", type_="foreignkey")
    op.drop_column("content_draft", "content_goal")
    op.drop_column("content_draft", "opportunity_id")
    op.drop_column("content_draft", "strategy_artifact_id")
    op.alter_column("content_draft", "experiment_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("content_draft", "account_id")
