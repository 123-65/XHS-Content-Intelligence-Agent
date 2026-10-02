"""add unified agent turn idempotency

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_turn",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "client_request_id", name="uq_agent_turn_account_request"),
    )
    op.create_index("ix_agent_turn_account_id", "agent_turn", ["account_id"])
    op.create_index("ix_agent_turn_conversation_id", "agent_turn", ["conversation_id"])
    op.create_index("ix_agent_turn_conversation_created", "agent_turn", ["conversation_id", "created_at"])


def downgrade():
    op.drop_index("ix_agent_turn_conversation_created", table_name="agent_turn")
    op.drop_index("ix_agent_turn_conversation_id", table_name="agent_turn")
    op.drop_index("ix_agent_turn_account_id", table_name="agent_turn")
    op.drop_table("agent_turn")
