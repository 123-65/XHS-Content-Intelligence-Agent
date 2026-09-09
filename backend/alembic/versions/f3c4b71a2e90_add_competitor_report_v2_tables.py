"""add competitor report v2 tables

Revision ID: f3c4b71a2e90
Revises: e2b0a1f9c8d3
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f3c4b71a2e90"
down_revision: Union[str, Sequence[str], None] = "e2b0a1f9c8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "competitor_analysis_report",
        sa.Column("competitor_account_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="参与分析的同行账号 ID"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("competitor_note_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="参与分析的竞品笔记 ID"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("comment_count", sa.Integer(), server_default="0", nullable=False, comment="参与分析的评论数量"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("persona_patterns", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="同行账号人设"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("content_pillars", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="内容支柱"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("cover_patterns", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="封面模式"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("content_structures", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="内容结构"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("comment_demands", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="评论需求"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("conversion_signals", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="转化信号"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("replicability_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="可复制性总结"),
    )
    op.add_column(
        "competitor_analysis_report",
        sa.Column("risk_points", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="风险点"),
    )

    op.create_table(
        "viral_note_breakdown",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False, comment="竞品分析报告 ID"),
        sa.Column("competitor_note_id", sa.Integer(), nullable=False, comment="竞品笔记 ID"),
        sa.Column("note_title", sa.String(length=512), nullable=True, comment="笔记标题"),
        sa.Column("note_url", sa.String(length=1024), nullable=True, comment="笔记链接"),
        sa.Column("engagement_score", sa.Float(), nullable=False, comment="互动表现分"),
        sa.Column("title_pattern", sa.String(length=64), nullable=False, comment="标题模式"),
        sa.Column("cover_pattern", sa.String(length=64), nullable=False, comment="封面模式"),
        sa.Column("content_structure", sa.String(length=64), nullable=False, comment="内容结构"),
        sa.Column("comment_demands", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="评论需求"),
        sa.Column("conversion_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="转化信号"),
        sa.Column("replicability_score", sa.Integer(), nullable=False, comment="可复制性评分"),
        sa.Column("risk_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="风险点"),
        sa.Column("evidence_summary", sa.Text(), nullable=False, comment="证据摘要"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competitor_note_id"], ["competitor_note.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["competitor_analysis_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_viral_note_breakdown_id"), "viral_note_breakdown", ["id"], unique=False)

    op.create_table(
        "content_opportunity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False, comment="竞品分析报告 ID"),
        sa.Column("opportunity_title", sa.String(length=256), nullable=False, comment="机会标题"),
        sa.Column("suggested_angle", sa.String(length=256), nullable=False, comment="建议角度"),
        sa.Column("target_audience", sa.String(length=128), nullable=True, comment="目标人群"),
        sa.Column("content_pillar", sa.String(length=64), nullable=False, comment="内容支柱"),
        sa.Column("comment_demand_type", sa.String(length=64), nullable=False, comment="评论需求类型"),
        sa.Column("evidence_summary", sa.Text(), nullable=False, comment="证据摘要"),
        sa.Column("replicability_score", sa.Integer(), nullable=False, comment="可复制性评分"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="风险等级"),
        sa.Column("risk_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="风险点"),
        sa.Column("opportunity_score", sa.Integer(), nullable=False, comment="机会评分"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["competitor_analysis_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_opportunity_id"), "content_opportunity", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_content_opportunity_id"), table_name="content_opportunity")
    op.drop_table("content_opportunity")
    op.drop_index(op.f("ix_viral_note_breakdown_id"), table_name="viral_note_breakdown")
    op.drop_table("viral_note_breakdown")
    op.drop_column("competitor_analysis_report", "risk_points")
    op.drop_column("competitor_analysis_report", "replicability_summary")
    op.drop_column("competitor_analysis_report", "conversion_signals")
    op.drop_column("competitor_analysis_report", "comment_demands")
    op.drop_column("competitor_analysis_report", "content_structures")
    op.drop_column("competitor_analysis_report", "cover_patterns")
    op.drop_column("competitor_analysis_report", "content_pillars")
    op.drop_column("competitor_analysis_report", "persona_patterns")
    op.drop_column("competitor_analysis_report", "comment_count")
    op.drop_column("competitor_analysis_report", "competitor_note_ids")
    op.drop_column("competitor_analysis_report", "competitor_account_ids")
