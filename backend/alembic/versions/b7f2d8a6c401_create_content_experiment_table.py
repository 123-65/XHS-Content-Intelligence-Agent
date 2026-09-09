"""create content experiment table

Revision ID: b7f2d8a6c401
Revises: 5858dc6da1be
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7f2d8a6c401"
down_revision: Union[str, Sequence[str], None] = "5858dc6da1be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "content_experiment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="账号 ID"),
        sa.Column("analysis_report_id", sa.Integer(), nullable=True, comment="关联竞品分析报告 ID"),
        sa.Column("experiment_name", sa.String(length=128), nullable=False, comment="实验名称"),
        sa.Column("hypothesis", sa.Text(), nullable=False, comment="实验假设"),
        sa.Column("target_metric", sa.String(length=32), nullable=False, comment="目标指标"),
        sa.Column("expected_result", sa.Text(), nullable=True, comment="预期结果"),
        sa.Column("topic_angle", sa.String(length=256), nullable=True, comment="选题角度"),
        sa.Column("selected_topic", sa.String(length=256), nullable=True, comment="最终选题"),
        sa.Column("target_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="目标数值"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="实验来源"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="实验状态"),
        sa.Column("publish_url", sa.String(length=1024), nullable=True, comment="发布后的笔记链接"),
        sa.Column("published_at", sa.DateTime(), nullable=True, comment="发布时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["analysis_report_id"], ["competitor_analysis_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_experiment_id"), "content_experiment", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_content_experiment_id"), table_name="content_experiment")
    op.drop_table("content_experiment")
