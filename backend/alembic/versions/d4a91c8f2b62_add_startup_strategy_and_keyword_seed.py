"""add startup strategy and keyword seed

Revision ID: d4a91c8f2b62
Revises: c8e71515f50d
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4a91c8f2b62"
down_revision: Union[str, Sequence[str], None] = "c8e71515f50d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("account_profile", sa.Column("content_domain", sa.String(length=128), nullable=True, comment="内容领域"))
    op.add_column("account_profile", sa.Column("persona", sa.Text(), nullable=True, comment="账号人设"))
    op.add_column("account_profile", sa.Column("monetization_goal", sa.String(length=128), nullable=True, comment="变现目标"))
    op.add_column(
        "account_profile",
        sa.Column("risk_preference", sa.String(length=32), server_default="BALANCED", nullable=False, comment="风险偏好"),
    )
    op.add_column(
        "account_profile",
        sa.Column("account_stage", sa.String(length=32), server_default="STARTUP", nullable=False, comment="账号阶段"),
    )

    op.create_table(
        "startup_strategy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="账号 ID"),
        sa.Column("strategy_name", sa.String(length=128), nullable=False, comment="策略名称"),
        sa.Column("persona_hypothesis", sa.Text(), nullable=True, comment="人设假设"),
        sa.Column("content_mix", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="内容组合"),
        sa.Column("success_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="成功标准"),
        sa.Column("adjustment_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="调整规则"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="策略状态"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_startup_strategy_id"), "startup_strategy", ["id"], unique=False)

    op.create_table(
        "keyword_seed",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="账号 ID"),
        sa.Column("keyword", sa.String(length=128), nullable=False, comment="关键词"),
        sa.Column("category", sa.String(length=64), nullable=False, comment="关键词分类"),
        sa.Column("reason", sa.Text(), nullable=True, comment="生成理由"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="来源类型"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="置信度"),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="原始生成快照"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="采集/生成时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_keyword_seed_id"), "keyword_seed", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_keyword_seed_id"), table_name="keyword_seed")
    op.drop_table("keyword_seed")
    op.drop_index(op.f("ix_startup_strategy_id"), table_name="startup_strategy")
    op.drop_table("startup_strategy")
    op.drop_column("account_profile", "account_stage")
    op.drop_column("account_profile", "risk_preference")
    op.drop_column("account_profile", "monetization_goal")
    op.drop_column("account_profile", "persona")
    op.drop_column("account_profile", "content_domain")
