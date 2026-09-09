"""add agent observability columns

Revision ID: b4c8e2f6a901
Revises: a2d5f7b9c310
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c8e2f6a901"
down_revision: Union[str, Sequence[str], None] = "a2d5f7b9c310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 Agent 可观测性字段。"""
    op.add_column("agent_run", sa.Column("agent_type", sa.String(length=64), server_default="WORKFLOW_AGENT", nullable=False, comment="Agent type"))
    op.add_column("agent_run", sa.Column("token_count", sa.Integer(), server_default="0", nullable=False, comment="Token count"))
    op.add_column("agent_run", sa.Column("estimated_cost", sa.Numeric(12, 6), server_default="0", nullable=False, comment="Estimated cost"))


def downgrade() -> None:
    """回滚 Agent 可观测性字段。"""
    op.drop_column("agent_run", "estimated_cost")
    op.drop_column("agent_run", "token_count")
    op.drop_column("agent_run", "agent_type")
