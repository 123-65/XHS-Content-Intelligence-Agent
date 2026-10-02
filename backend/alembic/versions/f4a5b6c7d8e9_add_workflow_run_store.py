"""add durable workflow run store

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_ref", sa.String(length=64), nullable=False),
        sa.Column("workflow_name", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account_profile.id"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pending_interaction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("checkpoint_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("workflow_name IN ('RESEARCH_V1','CONTENT_STRATEGY_V1','CONTENT_CREATION_V1','CONTENT_REFINEMENT_V1','POST_PUBLISH_REVIEW_V1')", name="ck_workflow_run_name"),
        sa.CheckConstraint("status IN ('PENDING','RUNNING','WAITING_USER','SUCCESS','PARTIAL_SUCCESS','FAILED','CANCELLED')", name="ck_workflow_run_status"),
        sa.CheckConstraint("checkpoint_version >= 1", name="ck_workflow_run_checkpoint_version"),
        sa.UniqueConstraint("run_ref", name="uq_workflow_run_run_ref"),
    )
    op.create_index("ix_workflow_run_account_id", "workflow_run", ["account_id"])
    op.create_index("ix_workflow_run_workflow_name", "workflow_run", ["workflow_name"])
    op.create_index("ix_workflow_run_status", "workflow_run", ["status"])
    op.create_index("ix_workflow_run_updated_at", "workflow_run", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_run_updated_at", table_name="workflow_run")
    op.drop_index("ix_workflow_run_status", table_name="workflow_run")
    op.drop_index("ix_workflow_run_workflow_name", table_name="workflow_run")
    op.drop_index("ix_workflow_run_account_id", table_name="workflow_run")
    op.drop_table("workflow_run")
