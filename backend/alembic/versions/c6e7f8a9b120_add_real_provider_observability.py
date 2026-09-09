"""add real provider observability

Revision ID: c6e7f8a9b120
Revises: b4c8e2f6a901
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6e7f8a9b120"
down_revision: Union[str, Sequence[str], None] = "b4c8e2f6a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级真实 Provider 灰度观测字段。"""
    for table_name in ("competitor_account", "competitor_note", "competitor_comment"):
        op.add_column(table_name, sa.Column("provider_name", sa.String(length=64), server_default="seed_sample", nullable=False, comment="Provider name"))
        op.add_column(table_name, sa.Column("is_mock", sa.Boolean(), server_default=sa.text("true"), nullable=False, comment="Is mock data"))
    op.add_column("prompt_run_log", sa.Column("prompt_key", sa.String(length=128), nullable=True, comment="Prompt key"))
    op.add_column("prompt_run_log", sa.Column("input_token_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("prompt_run_log", sa.Column("output_token_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("prompt_run_log", sa.Column("is_mock", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="Is mock provider"))


def downgrade() -> None:
    """回滚真实 Provider 灰度观测字段。"""
    op.drop_column("prompt_run_log", "is_mock")
    op.drop_column("prompt_run_log", "output_token_count")
    op.drop_column("prompt_run_log", "input_token_count")
    op.drop_column("prompt_run_log", "prompt_key")
    for table_name in ("competitor_comment", "competitor_note", "competitor_account"):
        op.drop_column(table_name, "is_mock")
        op.drop_column(table_name, "provider_name")
