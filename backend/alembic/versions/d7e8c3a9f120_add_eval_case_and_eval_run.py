"""add eval case and eval run

Revision ID: d7e8c3a9f120
Revises: bc29e82d4f65
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d7e8c3a9f120"
down_revision: Union[str, Sequence[str], None] = "bc29e82d4f65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "eval_case",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("suite_name", sa.String(length=128), nullable=False, comment="Suite name"),
        sa.Column("case_key", sa.String(length=128), nullable=False, comment="Stable case key"),
        sa.Column("eval_type", sa.String(length=64), nullable=False, comment="Evaluation type"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Input payload"),
        sa.Column("expected_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Expected output"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Case metadata"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="Is active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_case_id"), "eval_case", ["id"], unique=False)
    op.create_index("uq_eval_case_suite_key", "eval_case", ["suite_name", "case_key"], unique=True)

    op.create_table(
        "eval_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("eval_type", sa.String(length=64), nullable=False, comment="Evaluation type"),
        sa.Column("dataset_path", sa.String(length=512), nullable=False, comment="Dataset path"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Run status"),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("passed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("pass_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("failed_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Failed reasons"),
        sa.Column("report_path", sa.String(length=512), nullable=True, comment="Report path"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_run_id"), "eval_run", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_eval_run_id"), table_name="eval_run")
    op.drop_table("eval_run")
    op.drop_index("uq_eval_case_suite_key", table_name="eval_case")
    op.drop_index(op.f("ix_eval_case_id"), table_name="eval_case")
    op.drop_table("eval_case")
