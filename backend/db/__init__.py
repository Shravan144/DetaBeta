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


def init_db() -> None:
    """Create every table defined on Base if it does not already exist.

    Safe to call on every startup: SQLAlchemy issues CREATE TABLE IF NOT
    EXISTS-style statements, so existing data is left untouched. Importing the
    models above is what registers them on Base.metadata.
    """
    Base.metadata.create_all(bind=engine)


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
