"""add post publish feedback loop

Revision ID: f1b2c3d4e590
Revises: e9a1f63bd842
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1b2c3d4e590"
down_revision: Union[str, Sequence[str], None] = "e9a1f63bd842"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级发布后数据闭环相关表结构。"""
    op.create_table(
        "published_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("experiment_id", sa.Integer(), nullable=False, comment="Experiment ID"),
        sa.Column("draft_id", sa.Integer(), nullable=False, comment="Draft ID"),
        sa.Column("publish_url", sa.String(length=1024), nullable=False, comment="Published note URL"),
        sa.Column("platform", sa.String(length=32), nullable=False, comment="Platform"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Published note status"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="Source type"),
        sa.Column("published_at", sa.DateTime(), nullable=True, comment="Published at"),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Raw publish snapshot"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["content_draft.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["content_experiment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_published_note_id"), "published_note", ["id"], unique=False)

    op.create_table(
        "public_metric_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("published_note_id", sa.Integer(), nullable=False, comment="Published note ID"),
        sa.Column("snapshot_window", sa.String(length=16), nullable=False, comment="Snapshot window"),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False),
        sa.Column("collect_count", sa.Integer(), nullable=False),
        sa.Column("comment_count", sa.Integer(), nullable=False),
        sa.Column("share_count", sa.Integer(), nullable=False),
        sa.Column("follow_count", sa.Integer(), nullable=False),
        sa.Column("profile_visit_count", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="Source type"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Raw metric snapshot"),
        sa.ForeignKeyConstraint(["published_note_id"], ["published_note.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_public_metric_snapshot_id"), "public_metric_snapshot", ["id"], unique=False)
    op.create_index("ix_public_metric_snapshot_note_window", "public_metric_snapshot", ["published_note_id", "snapshot_window"], unique=False)

    op.create_table(
        "private_conversion_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("published_note_id", sa.Integer(), nullable=False, comment="Published note ID"),
        sa.Column("snapshot_window", sa.String(length=16), nullable=True, comment="Snapshot window"),
        sa.Column("dm_count", sa.Integer(), nullable=False),
        sa.Column("lead_count", sa.Integer(), nullable=False),
        sa.Column("wechat_add_count", sa.Integer(), nullable=False),
        sa.Column("group_join_count", sa.Integer(), nullable=False),
        sa.Column("consultation_count", sa.Integer(), nullable=False),
        sa.Column("price_inquiry_count", sa.Integer(), nullable=False),
        sa.Column("resource_request_count", sa.Integer(), nullable=False),
        sa.Column("deal_count", sa.Integer(), nullable=False),
        sa.Column("revenue_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="Source type"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Raw conversion snapshot"),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["published_note_id"], ["published_note.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_private_conversion_snapshot_id"), "private_conversion_snapshot", ["id"], unique=False)

    op.create_table(
        "note_comment_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("published_note_id", sa.Integer(), nullable=False, comment="Published note ID"),
        sa.Column("content", sa.Text(), nullable=False, comment="Comment content"),
        sa.Column("author_name", sa.String(length=128), nullable=True, comment="Author name"),
        sa.Column("like_count", sa.Integer(), nullable=False),
        sa.Column("demand_type", sa.String(length=64), nullable=False, comment="Demand type"),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="Source type"),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Raw comment snapshot"),
        sa.ForeignKeyConstraint(["published_note_id"], ["published_note.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_note_comment_snapshot_id"), "note_comment_snapshot", ["id"], unique=False)

    op.add_column("review_report", sa.Column("account_id", sa.Integer(), nullable=True, comment="Account ID"))
    op.add_column("review_report", sa.Column("experiment_id", sa.Integer(), nullable=True, comment="Experiment ID"))
    op.add_column("review_report", sa.Column("published_note_id", sa.Integer(), nullable=True, comment="Published note ID"))
    op.add_column("review_report", sa.Column("review_type", sa.String(length=32), server_default="CONTENT_REVIEW", nullable=False, comment="Review type"))
    op.add_column("review_report", sa.Column("result_status", sa.String(length=32), nullable=True, comment="Post-publish result status"))
    op.add_column("review_report", sa.Column("public_metrics_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Public metrics summary"))
    op.add_column("review_report", sa.Column("private_conversion_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Private conversion summary"))
    op.add_column("review_report", sa.Column("comment_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Comment summary"))
    op.add_column("review_report", sa.Column("data_facts", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Data facts"))
    op.add_column("review_report", sa.Column("inferences", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Inferences"))
    op.add_column("review_report", sa.Column("action_suggestions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Action suggestions"))
    op.create_foreign_key("fk_review_report_account_id", "review_report", "account_profile", ["account_id"], ["id"])
    op.create_foreign_key("fk_review_report_experiment_id", "review_report", "content_experiment", ["experiment_id"], ["id"])
    op.create_foreign_key("fk_review_report_published_note_id", "review_report", "published_note", ["published_note_id"], ["id"])

    op.create_table(
        "strategy_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("memory_type", sa.String(length=64), nullable=False, comment="Memory type"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Memory status"),
        sa.Column("summary", sa.Text(), nullable=False, comment="Memory summary"),
        sa.Column("pattern", sa.Text(), nullable=True, comment="Reusable pattern"),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source_review_report_id", sa.Integer(), nullable=True, comment="Source review report ID"),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="Risk level"),
        sa.Column("metadata_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Metadata payload"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["source_review_report_id"], ["review_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strategy_memory_id"), "strategy_memory", ["id"], unique=False)
    op.create_index("ix_strategy_memory_account_type", "strategy_memory", ["account_id", "memory_type"], unique=False)

    op.create_table(
        "memory_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=False, comment="Memory ID"),
        sa.Column("review_report_id", sa.Integer(), nullable=False, comment="Review report ID"),
        sa.Column("evidence_type", sa.String(length=32), nullable=False, comment="FACT, INFERENCE, or SUGGESTION"),
        sa.Column("evidence_text", sa.Text(), nullable=False, comment="Evidence text"),
        sa.Column("evidence_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Evidence payload"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memory_id"], ["strategy_memory.id"]),
        sa.ForeignKeyConstraint(["review_report_id"], ["review_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_evidence_id"), "memory_evidence", ["id"], unique=False)

    op.create_table(
        "content_optimization_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("source_review_report_id", sa.Integer(), nullable=False, comment="Source review report ID"),
        sa.Column("plan_type", sa.String(length=32), nullable=False, comment="Plan type"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Plan status"),
        sa.Column("summary", sa.Text(), nullable=False, comment="Plan summary"),
        sa.Column("rationale", sa.Text(), nullable=False, comment="Plan rationale"),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Optimization actions"),
        sa.Column("generated_experiment_id", sa.Integer(), nullable=True, comment="Generated experiment ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["generated_experiment_id"], ["content_experiment.id"]),
        sa.ForeignKeyConstraint(["source_review_report_id"], ["review_report.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_optimization_plan_id"), "content_optimization_plan", ["id"], unique=False)


def downgrade() -> None:
    """回滚发布后数据闭环相关表结构。"""
    op.drop_index(op.f("ix_content_optimization_plan_id"), table_name="content_optimization_plan")
    op.drop_table("content_optimization_plan")
    op.drop_index(op.f("ix_memory_evidence_id"), table_name="memory_evidence")
    op.drop_table("memory_evidence")
    op.drop_index("ix_strategy_memory_account_type", table_name="strategy_memory")
    op.drop_index(op.f("ix_strategy_memory_id"), table_name="strategy_memory")
    op.drop_table("strategy_memory")
    op.drop_constraint("fk_review_report_published_note_id", "review_report", type_="foreignkey")
    op.drop_constraint("fk_review_report_experiment_id", "review_report", type_="foreignkey")
    op.drop_constraint("fk_review_report_account_id", "review_report", type_="foreignkey")
    op.drop_column("review_report", "action_suggestions")
    op.drop_column("review_report", "inferences")
    op.drop_column("review_report", "data_facts")
    op.drop_column("review_report", "comment_summary")
    op.drop_column("review_report", "private_conversion_summary")
    op.drop_column("review_report", "public_metrics_summary")
    op.drop_column("review_report", "result_status")
    op.drop_column("review_report", "review_type")
    op.drop_column("review_report", "published_note_id")
    op.drop_column("review_report", "experiment_id")
    op.drop_column("review_report", "account_id")
    op.drop_index(op.f("ix_note_comment_snapshot_id"), table_name="note_comment_snapshot")
    op.drop_table("note_comment_snapshot")
    op.drop_index(op.f("ix_private_conversion_snapshot_id"), table_name="private_conversion_snapshot")
    op.drop_table("private_conversion_snapshot")
    op.drop_index("ix_public_metric_snapshot_note_window", table_name="public_metric_snapshot")
    op.drop_index(op.f("ix_public_metric_snapshot_id"), table_name="public_metric_snapshot")
    op.drop_table("public_metric_snapshot")
    op.drop_index(op.f("ix_published_note_id"), table_name="published_note")
    op.drop_table("published_note")
