"""create content draft and review report tables

Revision ID: c8e71515f50d
Revises: b7f2d8a6c401
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c8e71515f50d"
down_revision: Union[str, Sequence[str], None] = "b7f2d8a6c401"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "content_draft",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False, comment="内容实验 ID"),
        sa.Column("title", sa.String(length=512), nullable=False, comment="小红书标题"),
        sa.Column("body", sa.Text(), nullable=False, comment="小红书正文"),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="标签列表"),
        sa.Column("cover_text", sa.String(length=256), nullable=True, comment="封面文案"),
        sa.Column("image_scripts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="图片脚本"),
        sa.Column("cta", sa.Text(), nullable=True, comment="转化引导语"),
        sa.Column("version", sa.Integer(), nullable=False, comment="草稿版本"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="草稿状态"),
        sa.Column("generation_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="生成上下文快照"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("raw_response_id", sa.String(length=128), nullable=True, comment="模型响应 ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["content_experiment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_draft_id"), "content_draft", ["id"], unique=False)

    op.create_table(
        "review_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False, comment="草稿 ID"),
        sa.Column("passed", sa.Boolean(), nullable=False, comment="是否审核通过"),
        sa.Column("score", sa.Integer(), nullable=False, comment="综合评分"),
        sa.Column("quality_score", sa.Integer(), nullable=False, comment="内容质量评分"),
        sa.Column("conversion_score", sa.Integer(), nullable=False, comment="转化引导评分"),
        sa.Column("evidence_usage_score", sa.Integer(), nullable=False, comment="证据使用评分"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="风险等级"),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="问题列表"),
        sa.Column("suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="修改建议"),
        sa.Column("summary", sa.Text(), nullable=True, comment="审核总结"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="审核状态"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("raw_response_id", sa.String(length=128), nullable=True, comment="模型响应 ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["content_draft.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_report_id"), "review_report", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_review_report_id"), table_name="review_report")
    op.drop_table("review_report")
    op.drop_index(op.f("ix_content_draft_id"), table_name="content_draft")
    op.drop_table("content_draft")
