"""add workflow execution lease

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""
from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workflow_run", sa.Column("execution_token", sa.String(length=64), nullable=True))
    op.add_column("workflow_run", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column("workflow_run", sa.Column("execution_mode", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("workflow_run", "execution_mode")
    op.drop_column("workflow_run", "lease_expires_at")
    op.drop_column("workflow_run", "execution_token")
