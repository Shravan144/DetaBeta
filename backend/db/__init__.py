"""Database package: SQLAlchemy engine, session, and ORM models.

Public surface:
    Base, engine, SessionLocal, get_db          -- from session.py
    Project, Dataset,
    AnalysisSession, EngineResult               -- from models.py
    init_db()                                   -- create all tables if missing
"""

from __future__ import annotations

from db.models import AnalysisSession, Dataset, EngineResult, Project
from db.session import Base, SessionLocal, engine, get_db


from sqlalchemy import inspect, text


def init_db() -> None:
    """Create every table defined on Base if it does not already exist.

    Safe to call on every startup: SQLAlchemy issues CREATE TABLE IF NOT
    EXISTS-style statements, so existing data is left untouched. Importing the
    models above is what registers them on Base.metadata.
    """
    Base.metadata.create_all(bind=engine)

    # Lightweight auto-migration: ensure projects table has user_id column
    # on pre-existing databases created before auth was added.
    inspector = inspect(engine)
    if "projects" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("projects")]
        if "user_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE projects ADD COLUMN user_id VARCHAR(255)"))


__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "Project",
    "Dataset",
    "AnalysisSession",
    "EngineResult",
    "init_db",
]
