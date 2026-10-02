"""add exact publish version lineage

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("publish_package", sa.Column("draft_version_id", sa.Integer(), nullable=True))
    op.add_column("publish_package", sa.Column("version_number", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_publish_package_draft_version", "publish_package", "content_draft_version", ["draft_version_id"], ["id"])
    op.create_index("ix_publish_package_draft_version_id", "publish_package", ["draft_version_id"])
    op.add_column("published_note", sa.Column("draft_version_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_published_note_draft_version", "published_note", "content_draft_version", ["draft_version_id"], ["id"])
    op.create_index("ix_published_note_draft_version_id", "published_note", ["draft_version_id"])
    op.alter_column("published_note", "experiment_id", existing_type=sa.Integer(), nullable=True)

def downgrade():
    op.alter_column("published_note", "experiment_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_published_note_draft_version_id", table_name="published_note")
    op.drop_constraint("fk_published_note_draft_version", "published_note", type_="foreignkey")
    op.drop_column("published_note", "draft_version_id")
    op.drop_index("ix_publish_package_draft_version_id", table_name="publish_package")
    op.drop_constraint("fk_publish_package_draft_version", "publish_package", type_="foreignkey")
    op.drop_column("publish_package", "version_number")
    op.drop_column("publish_package", "draft_version_id")
