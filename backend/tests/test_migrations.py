"""Regression tests for the versioned database schema."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_creates_all_application_tables(tmp_path: Path) -> None:
    """A blank database must become usable through ``alembic upgrade head``.

    This fails if a migration is missing a table, an index/foreign-key change
    is only made in SQLAlchemy models, or the migration command is not wired to
    the application's metadata.
    """
    db_path = tmp_path / "migrated.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_ROOT / "alembic.ini"),
            "upgrade",
            "head",
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    engine = create_engine(f"sqlite:///{db_path}")
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "analysis_sessions",
        "datasets",
        "engine_results",
        "projects",
    }
    project_columns = {
        column["name"] for column in inspect(engine).get_columns("projects")
    }
    assert "user_id" in project_columns


def test_offline_migration_accepts_standard_postgres_urls() -> None:
    """Supabase's ``postgresql://`` URI must use the installed psycopg driver."""
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://user:pass%40word@db.example.test:5432/detabeta"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_ROOT / "alembic.ini"),
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE projects" in result.stdout
