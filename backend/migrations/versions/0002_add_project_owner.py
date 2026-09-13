"""Add the authenticated owner field to projects.

Revision ID: 0002_add_project_owner
Revises: 0001_initial_schema
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_project_owner"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable retains pre-auth rows for an explicit ownership migration.
    op.add_column("projects", sa.Column("user_id", sa.String(length=255), nullable=True))
    op.create_index("ix_projects_user_id", "projects", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_column("projects", "user_id")
