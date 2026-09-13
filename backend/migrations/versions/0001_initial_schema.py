"""Create the initial DetaBeta persistence schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("n_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_columns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_analysis_sessions_dataset_id", "analysis_sessions", ["dataset_id"])
    op.create_table(
        "engine_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("engine_key", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["analysis_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "engine_key", name="uq_engine_per_session"),
    )
    op.create_index("ix_engine_results_session_id", "engine_results", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_engine_results_session_id", table_name="engine_results")
    op.drop_table("engine_results")
    op.drop_index("ix_analysis_sessions_dataset_id", table_name="analysis_sessions")
    op.drop_table("analysis_sessions")
    op.drop_index("ix_datasets_project_id", table_name="datasets")
    op.drop_table("datasets")
    op.drop_table("projects")
