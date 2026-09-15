"""add agent conversation tables

Revision ID: b1c2d3e4f5a6
Revises: ac23d4e5f6a7
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "ac23d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_conversation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True, comment="Active account ID"),
        sa.Column("title", sa.String(length=128), server_default="新会话", nullable=False, comment="Conversation title"),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False, comment="Conversation status"),
        sa.Column("current_state", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Current conversation state"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True, comment="Last message time"),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_conversation_id"), "agent_conversation", ["id"], unique=False)
    op.create_index(op.f("ix_agent_conversation_account_id"), "agent_conversation", ["account_id"], unique=False)
    op.create_index(op.f("ix_agent_conversation_status"), "agent_conversation", ["status"], unique=False)
    op.create_index(op.f("ix_agent_conversation_last_message_at"), "agent_conversation", ["last_message_at"], unique=False)

    op.create_table(
        "agent_conversation_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False, comment="Conversation ID"),
        sa.Column("role", sa.String(length=32), nullable=False, comment="Message role"),
        sa.Column("content", sa.Text(), nullable=False, comment="Message content"),
        sa.Column("message_type", sa.String(length=32), server_default="TEXT", nullable=False, comment="Message type"),
        sa.Column("metadata_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False, comment="Safe message metadata"),
        sa.Column("trace_id", sa.String(length=128), nullable=True, comment="Agent trace ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_conversation_message_id"), "agent_conversation_message", ["id"], unique=False)
    op.create_index(op.f("ix_agent_conversation_message_conversation_id"), "agent_conversation_message", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_agent_conversation_message_role"), "agent_conversation_message", ["role"], unique=False)
    op.create_index(op.f("ix_agent_conversation_message_message_type"), "agent_conversation_message", ["message_type"], unique=False)
    op.create_index(op.f("ix_agent_conversation_message_trace_id"), "agent_conversation_message", ["trace_id"], unique=False)
    op.create_index(op.f("ix_agent_conversation_message_created_at"), "agent_conversation_message", ["created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_agent_conversation_message_created_at"), table_name="agent_conversation_message")
    op.drop_index(op.f("ix_agent_conversation_message_trace_id"), table_name="agent_conversation_message")
    op.drop_index(op.f("ix_agent_conversation_message_message_type"), table_name="agent_conversation_message")
    op.drop_index(op.f("ix_agent_conversation_message_role"), table_name="agent_conversation_message")
    op.drop_index(op.f("ix_agent_conversation_message_conversation_id"), table_name="agent_conversation_message")
    op.drop_index(op.f("ix_agent_conversation_message_id"), table_name="agent_conversation_message")
    op.drop_table("agent_conversation_message")
    op.drop_index(op.f("ix_agent_conversation_last_message_at"), table_name="agent_conversation")
    op.drop_index(op.f("ix_agent_conversation_status"), table_name="agent_conversation")
    op.drop_index(op.f("ix_agent_conversation_account_id"), table_name="agent_conversation")
    op.drop_index(op.f("ix_agent_conversation_id"), table_name="agent_conversation")
    op.drop_table("agent_conversation")
