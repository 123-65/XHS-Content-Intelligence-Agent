"""add agent runtime tables

Revision ID: a2d5f7b9c310
Revises: f1b2c3d4e590
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a2d5f7b9c310"
down_revision: Union[str, Sequence[str], None] = "f1b2c3d4e590"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 Agent Runtime、Tool Registry 和 MCP Gateway 表结构。"""
    op.create_table(
        "agent_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True, comment="Account ID"),
        sa.Column("workflow_name", sa.String(length=128), nullable=False, comment="Workflow name"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Run status"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Run input"),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Run output"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message"),
        sa.Column("stop_reason", sa.String(length=64), nullable=True, comment="Stop reason"),
        sa.Column("max_steps", sa.Integer(), nullable=False, comment="Max steps"),
        sa.Column("max_retry", sa.Integer(), nullable=False, comment="Max retry"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, comment="Consecutive failures"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_run_id"), "agent_run", ["id"], unique=False)
    op.create_index(op.f("ix_agent_run_account_id"), "agent_run", ["account_id"], unique=False)

    op.create_table(
        "agent_step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=False, comment="Agent run ID"),
        sa.Column("step_index", sa.Integer(), nullable=False, comment="Step index"),
        sa.Column("tool_name", sa.String(length=128), nullable=False, comment="Tool name"),
        sa.Column("tool_type", sa.String(length=32), nullable=False, comment="Tool type"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Step status"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Tool input"),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Tool output"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message"),
        sa.Column("retry_count", sa.Integer(), nullable=False, comment="Retry count"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="Risk level"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, comment="Requires confirmation"),
        sa.Column("fallback_tool_name", sa.String(length=128), nullable=True, comment="Fallback tool name"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, comment="Duration milliseconds"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_step_id"), "agent_step", ["id"], unique=False)
    op.create_index(op.f("ix_agent_step_agent_run_id"), "agent_step", ["agent_run_id"], unique=False)

    op.create_table(
        "mcp_server_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_name", sa.String(length=128), nullable=False, comment="Server name"),
        sa.Column("base_url", sa.String(length=1024), nullable=True, comment="Base URL"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Server status"),
        sa.Column("auth_type", sa.String(length=32), nullable=False, comment="Auth type"),
        sa.Column("allowed_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Allowed tools"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="Risk level"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, comment="Requires confirmation"),
        sa.Column("description", sa.Text(), nullable=True, comment="Description"),
        sa.Column("metadata_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Metadata payload"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_server_config_id"), "mcp_server_config", ["id"], unique=False)
    op.create_unique_constraint("uq_mcp_server_config_server_name", "mcp_server_config", ["server_name"])

    op.create_table(
        "mcp_tool_binding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_config_id", sa.Integer(), nullable=True, comment="Server config ID"),
        sa.Column("tool_name", sa.String(length=128), nullable=False, comment="Tool name"),
        sa.Column("display_name", sa.String(length=128), nullable=False, comment="Display name"),
        sa.Column("description", sa.Text(), nullable=True, comment="Description"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="Risk level"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, comment="Requires confirmation"),
        sa.Column("fallback_tool_name", sa.String(length=128), nullable=True, comment="Fallback tool name"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="Enabled"),
        sa.Column("whitelist_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Whitelist rules"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["server_config_id"], ["mcp_server_config.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_tool_binding_id"), "mcp_tool_binding", ["id"], unique=False)
    op.create_unique_constraint("uq_mcp_tool_binding_tool_name", "mcp_tool_binding", ["tool_name"])

    op.create_table(
        "mcp_tool_call_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True, comment="Agent run ID"),
        sa.Column("agent_step_id", sa.Integer(), nullable=True, comment="Agent step ID"),
        sa.Column("server_config_id", sa.Integer(), nullable=True, comment="Server config ID"),
        sa.Column("tool_name", sa.String(length=128), nullable=False, comment="Tool name"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Call status"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Tool input"),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Tool output"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, comment="Latency milliseconds"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, comment="Risk level"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, comment="Requires confirmation"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"]),
        sa.ForeignKeyConstraint(["agent_step_id"], ["agent_step.id"]),
        sa.ForeignKeyConstraint(["server_config_id"], ["mcp_server_config.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_tool_call_log_id"), "mcp_tool_call_log", ["id"], unique=False)

    op.create_table(
        "strategy_memory_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("agent_run_id", sa.Integer(), nullable=False, comment="Agent run ID"),
        sa.Column("memory_id", sa.Integer(), nullable=True, comment="Memory ID"),
        sa.Column("usage_reason", sa.Text(), nullable=False, comment="Usage reason"),
        sa.Column("usage_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Usage snapshot"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["strategy_memory.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strategy_memory_usage_id"), "strategy_memory_usage", ["id"], unique=False)
    op.create_index(op.f("ix_strategy_memory_usage_account_id"), "strategy_memory_usage", ["account_id"], unique=False)


def downgrade() -> None:
    """回滚 Agent Runtime、Tool Registry 和 MCP Gateway 表结构。"""
    op.drop_index(op.f("ix_strategy_memory_usage_account_id"), table_name="strategy_memory_usage")
    op.drop_index(op.f("ix_strategy_memory_usage_id"), table_name="strategy_memory_usage")
    op.drop_table("strategy_memory_usage")
    op.drop_index(op.f("ix_mcp_tool_call_log_id"), table_name="mcp_tool_call_log")
    op.drop_table("mcp_tool_call_log")
    op.drop_constraint("uq_mcp_tool_binding_tool_name", "mcp_tool_binding", type_="unique")
    op.drop_index(op.f("ix_mcp_tool_binding_id"), table_name="mcp_tool_binding")
    op.drop_table("mcp_tool_binding")
    op.drop_constraint("uq_mcp_server_config_server_name", "mcp_server_config", type_="unique")
    op.drop_index(op.f("ix_mcp_server_config_id"), table_name="mcp_server_config")
    op.drop_table("mcp_server_config")
    op.drop_index(op.f("ix_agent_step_agent_run_id"), table_name="agent_step")
    op.drop_index(op.f("ix_agent_step_id"), table_name="agent_step")
    op.drop_table("agent_step")
    op.drop_index(op.f("ix_agent_run_account_id"), table_name="agent_run")
    op.drop_index(op.f("ix_agent_run_id"), table_name="agent_run")
    op.drop_table("agent_run")
