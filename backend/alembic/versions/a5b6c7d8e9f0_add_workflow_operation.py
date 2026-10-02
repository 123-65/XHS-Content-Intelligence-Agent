"""add workflow operation ledger

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_operation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_ref", sa.String(length=64), nullable=False),
        sa.Column("workflow_name", sa.String(length=64), nullable=False),
        sa.Column("operation_key", sa.String(length=160), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("identity_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_ref"], ["workflow_run.run_ref"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_ref", "operation_key", name="uq_workflow_operation_run_key"),
    )
    op.create_index("ix_workflow_operation_run_ref", "workflow_operation", ["run_ref"])
    op.create_index("ix_workflow_operation_tool_name", "workflow_operation", ["tool_name"])


def downgrade():
    op.drop_index("ix_workflow_operation_tool_name", table_name="workflow_operation")
    op.drop_index("ix_workflow_operation_run_ref", table_name="workflow_operation")
    op.drop_table("workflow_operation")
