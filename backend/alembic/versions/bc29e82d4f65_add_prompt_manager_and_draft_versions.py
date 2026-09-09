"""add prompt manager and draft versions

Revision ID: bc29e82d4f65
Revises: a54b2e830c71
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "bc29e82d4f65"
down_revision: Union[str, Sequence[str], None] = "a54b2e830c71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "content_draft",
        sa.Column("title_candidates", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Title candidates"),
    )
    op.add_column("content_draft", sa.Column("recommended_title", sa.String(length=512), nullable=True, comment="Recommended title"))
    op.add_column("content_draft", sa.Column("cover_subtitle", sa.String(length=256), nullable=True, comment="Cover subtitle"))
    op.add_column("content_draft", sa.Column("body_text", sa.Text(), nullable=True, comment="Draft body text"))
    op.add_column(
        "content_draft",
        sa.Column("image_script", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Image script"),
    )
    op.add_column(
        "content_draft",
        sa.Column("tag_list", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Tag list"),
    )
    op.add_column(
        "content_draft",
        sa.Column("keyword_list", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False, comment="Keyword list"),
    )
    op.add_column("content_draft", sa.Column("cta_text", sa.Text(), nullable=True, comment="CTA text"))

    op.create_table(
        "prompt_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_name", sa.String(length=128), nullable=False, comment="Prompt name"),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, comment="Prompt version"),
        sa.Column("template_path", sa.String(length=256), nullable=False, comment="Template path"),
        sa.Column("system_prompt", sa.Text(), nullable=False, comment="System prompt"),
        sa.Column("user_template", sa.Text(), nullable=False, comment="User prompt template"),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Output JSON schema"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Template status"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prompt_template_id"), "prompt_template", ["id"], unique=False)
    op.create_index("uq_prompt_template_name_version", "prompt_template", ["prompt_name", "prompt_version"], unique=True)

    op.create_table(
        "prompt_run_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_template_id", sa.Integer(), nullable=True, comment="Prompt template ID"),
        sa.Column("prompt_name", sa.String(length=128), nullable=False, comment="Prompt name"),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, comment="Prompt version"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Input payload snapshot"),
        sa.Column("rendered_prompt", sa.Text(), nullable=False, comment="Rendered prompt"),
        sa.Column("output_text", sa.Text(), nullable=True, comment="Raw model output"),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Structured output"),
        sa.Column("model", sa.String(length=128), nullable=False, comment="Model"),
        sa.Column("provider", sa.String(length=64), nullable=False, comment="Provider"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("raw_response_id", sa.String(length=128), nullable=True, comment="Raw response ID"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Run status"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["prompt_template_id"], ["prompt_template.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prompt_run_log_id"), "prompt_run_log", ["id"], unique=False)

    op.create_table(
        "draft_generation_context",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=True, comment="Draft ID"),
        sa.Column("account_id", sa.Integer(), nullable=False, comment="Account ID"),
        sa.Column("experiment_id", sa.Integer(), nullable=False, comment="Experiment ID"),
        sa.Column("content_opportunity_id", sa.Integer(), nullable=True, comment="Opportunity ID"),
        sa.Column("account_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Account snapshot"),
        sa.Column("experiment_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Experiment snapshot"),
        sa.Column("opportunity_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Opportunity snapshot"),
        sa.Column("strategy_memory_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Strategy memory snapshot"),
        sa.Column("risk_constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Risk constraints"),
        sa.Column("user_requirement", sa.String(length=1024), nullable=True, comment="User requirement"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account_profile.id"]),
        sa.ForeignKeyConstraint(["content_opportunity_id"], ["content_opportunity.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["content_draft.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["content_experiment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_draft_generation_context_id"), "draft_generation_context", ["id"], unique=False)

    op.create_table(
        "content_draft_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False, comment="Draft ID"),
        sa.Column("version", sa.Integer(), nullable=False, comment="Version number"),
        sa.Column("regenerate_scope", sa.String(length=32), nullable=False, comment="Regenerate scope"),
        sa.Column("draft_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Draft snapshot"),
        sa.Column("prompt_run_log_id", sa.Integer(), nullable=True, comment="Prompt run log ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["content_draft.id"]),
        sa.ForeignKeyConstraint(["prompt_run_log_id"], ["prompt_run_log.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_draft_version_id"), "content_draft_version", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_content_draft_version_id"), table_name="content_draft_version")
    op.drop_table("content_draft_version")
    op.drop_index(op.f("ix_draft_generation_context_id"), table_name="draft_generation_context")
    op.drop_table("draft_generation_context")
    op.drop_index(op.f("ix_prompt_run_log_id"), table_name="prompt_run_log")
    op.drop_table("prompt_run_log")
    op.drop_index("uq_prompt_template_name_version", table_name="prompt_template")
    op.drop_index(op.f("ix_prompt_template_id"), table_name="prompt_template")
    op.drop_table("prompt_template")
    op.drop_column("content_draft", "cta_text")
    op.drop_column("content_draft", "keyword_list")
    op.drop_column("content_draft", "tag_list")
    op.drop_column("content_draft", "image_script")
    op.drop_column("content_draft", "body_text")
    op.drop_column("content_draft", "cover_subtitle")
    op.drop_column("content_draft", "recommended_title")
    op.drop_column("content_draft", "title_candidates")
