"""Alembic environment for DetaBeta's SQLAlchemy schema."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv

# Load local settings before importing db.session: that module resolves its
# engine at import time. Hosted environments already provide these variables.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from alembic import context
from sqlalchemy import engine_from_config, pool

from db.models import AnalysisSession, Dataset, EngineResult, Project  # noqa: F401
from db.session import Base, DATABASE_URL

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Reuse the application normalizer: Supabase URLs become psycopg URLs and
# request SSL, matching the engine used by FastAPI itself.
# ConfigParser reserves "%" for interpolation; retain URL-encoded password
# characters by escaping them only while passing through Alembic's INI config.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live SQLAlchemy connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through a short-lived connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
