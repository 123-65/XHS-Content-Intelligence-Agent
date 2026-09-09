"""add experiment cards

Revision ID: a54b2e830c71
Revises: f3c4b71a2e90
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a54b2e830c71"
down_revision: Union[str, Sequence[str], None] = "f3c4b71a2e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "content_experiment",
        sa.Column("content_opportunity_id", sa.Integer(), nullable=True, comment="关联内容机会 ID"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("content_pillar", sa.String(length=64), server_default="未分类", nullable=False, comment="内容支柱"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("content_format", sa.String(length=64), server_default="图文笔记", nullable=False, comment="内容形式"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("main_variable", sa.String(length=128), nullable=True, comment="主变量"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("control_variables", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="控制变量"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("primary_metric", sa.String(length=64), server_default="collect", nullable=False, comment="主指标"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("secondary_metrics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="辅助指标"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("success_criteria", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="成功标准"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("failure_criteria", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="失败标准"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("fallback_strategy", sa.Text(), nullable=True, comment="失败兜底策略"),
    )
    op.add_column(
        "content_experiment",
        sa.Column("risk_level", sa.String(length=32), server_default="LOW", nullable=False, comment="风险等级"),
    )
    op.create_foreign_key(
        "fk_content_experiment_content_opportunity_id",
        "content_experiment",
        "content_opportunity",
        ["content_opportunity_id"],
        ["id"],
    )

    op.create_table(
        "experiment_variable",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False, comment="内容实验 ID"),
        sa.Column("variable_name", sa.String(length=128), nullable=False, comment="变量名称"),
        sa.Column("variable_type", sa.String(length=32), nullable=False, comment="变量类型"),
        sa.Column("variable_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="变量取值"),
        sa.Column("description", sa.Text(), nullable=True, comment="变量说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["content_experiment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiment_variable_id"), "experiment_variable", ["id"], unique=False)

    op.create_table(
        "experiment_metric_target",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False, comment="内容实验 ID"),
        sa.Column("metric_name", sa.String(length=64), nullable=False, comment="指标名称"),
        sa.Column("metric_type", sa.String(length=32), nullable=False, comment="指标类型"),
        sa.Column("target_value", sa.Numeric(precision=12, scale=2), nullable=False, comment="目标值"),
        sa.Column("comparison_operator", sa.String(length=16), nullable=False, comment="比较符"),
        sa.Column("description", sa.Text(), nullable=True, comment="指标说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["content_experiment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiment_metric_target_id"), "experiment_metric_target", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_experiment_metric_target_id"), table_name="experiment_metric_target")
    op.drop_table("experiment_metric_target")
    op.drop_index(op.f("ix_experiment_variable_id"), table_name="experiment_variable")
    op.drop_table("experiment_variable")
    op.drop_constraint("fk_content_experiment_content_opportunity_id", "content_experiment", type_="foreignkey")
    op.drop_column("content_experiment", "risk_level")
    op.drop_column("content_experiment", "fallback_strategy")
    op.drop_column("content_experiment", "failure_criteria")
    op.drop_column("content_experiment", "success_criteria")
    op.drop_column("content_experiment", "secondary_metrics")
    op.drop_column("content_experiment", "primary_metric")
    op.drop_column("content_experiment", "control_variables")
    op.drop_column("content_experiment", "main_variable")
    op.drop_column("content_experiment", "content_format")
    op.drop_column("content_experiment", "content_pillar")
    op.drop_column("content_experiment", "content_opportunity_id")
