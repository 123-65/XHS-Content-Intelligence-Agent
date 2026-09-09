"""create crawl provider competitor tables

Revision ID: e2b0a1f9c8d3
Revises: d4a91c8f2b62
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e2b0a1f9c8d3"
down_revision: Union[str, Sequence[str], None] = "d4a91c8f2b62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "crawl_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="账号 ID"),
        sa.Column("task_type", sa.String(length=64), nullable=False, comment="任务类型"),
        sa.Column("provider_name", sa.String(length=64), nullable=False, comment="采集 Provider 名称"),
        sa.Column("keyword", sa.String(length=128), nullable=True, comment="采集关键词"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="任务状态"),
        sa.Column("result_count", sa.Integer(), nullable=False, comment="结果总数"),
        sa.Column("success_count", sa.Integer(), nullable=False, comment="成功数量"),
        sa.Column("failed_count", sa.Integer(), nullable=False, comment="失败数量"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="整体置信度"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="任务输入快照"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="结束时间"),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_crawl_task_id"), "crawl_task", ["id"], unique=False)

    op.create_table(
        "competitor_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="本系统账号 ID"),
        sa.Column("platform", sa.String(length=32), nullable=False, comment="平台"),
        sa.Column("platform_account_id", sa.String(length=128), nullable=True, comment="平台账号 ID"),
        sa.Column("nickname", sa.String(length=128), nullable=False, comment="同行账号昵称"),
        sa.Column("homepage_url", sa.String(length=1024), nullable=True, comment="主页链接"),
        sa.Column("bio", sa.Text(), nullable=True, comment="简介"),
        sa.Column("follower_count", sa.Integer(), nullable=True, comment="粉丝数"),
        sa.Column("note_count", sa.Integer(), nullable=True, comment="笔记数"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="来源类型"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="采集时间"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="置信度"),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="原始快照"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_competitor_account_id"), "competitor_account", ["id"], unique=False)

    op.create_table(
        "competitor_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="本系统账号 ID"),
        sa.Column("competitor_account_id", sa.Integer(), nullable=True, comment="同行账号快照 ID"),
        sa.Column("note_id", sa.String(length=128), nullable=True, comment="平台笔记 ID"),
        sa.Column("note_url", sa.String(length=1024), nullable=True, comment="笔记链接"),
        sa.Column("author_name", sa.String(length=128), nullable=True, comment="作者昵称"),
        sa.Column("title", sa.String(length=512), nullable=True, comment="标题"),
        sa.Column("content", sa.Text(), nullable=True, comment="正文"),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="标签列表"),
        sa.Column("like_count", sa.Integer(), nullable=True, comment="点赞数"),
        sa.Column("collect_count", sa.Integer(), nullable=True, comment="收藏数"),
        sa.Column("comment_count", sa.Integer(), nullable=True, comment="评论数"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="来源类型"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="采集时间"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="置信度"),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="原始快照"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["competitor_account_id"], ["competitor_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_competitor_note_id"), "competitor_note", ["id"], unique=False)

    op.create_table(
        "competitor_comment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="本系统账号 ID"),
        sa.Column("competitor_note_id", sa.Integer(), nullable=True, comment="竞品笔记快照 ID"),
        sa.Column("comment_id", sa.String(length=128), nullable=True, comment="平台评论 ID"),
        sa.Column("user_name", sa.String(length=128), nullable=True, comment="评论用户"),
        sa.Column("content", sa.Text(), nullable=False, comment="评论内容"),
        sa.Column("like_count", sa.Integer(), nullable=True, comment="评论点赞数"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="来源类型"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="采集时间"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="置信度"),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="原始快照"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["competitor_note_id"], ["competitor_note.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_competitor_comment_id"), "competitor_comment", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_competitor_comment_id"), table_name="competitor_comment")
    op.drop_table("competitor_comment")
    op.drop_index(op.f("ix_competitor_note_id"), table_name="competitor_note")
    op.drop_table("competitor_note")
    op.drop_index(op.f("ix_competitor_account_id"), table_name="competitor_account")
    op.drop_table("competitor_account")
    op.drop_index(op.f("ix_crawl_task_id"), table_name="crawl_task")
    op.drop_table("crawl_task")
