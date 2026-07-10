"""
Database session & engine setup (SQLAlchemy 2.0 style).

WHY THIS FILE EXISTS
--------------------
Every part of the app that touches the database needs two things:
  1. A configured "engine" that knows *where* the database is.
  2. A way to open a short-lived "session" (a conversation with the DB) and
     reliably close it again.

We keep both here, in one place, so the rest of the code never worries about
connection details. In development we use SQLite (a single file on disk, zero
setup). Later we can point DATABASE_URL at PostgreSQL without changing any of
the models, services, or routes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Where is the database?
# ---------------------------------------------------------------------------
# Default: a file called `detabeta.db` inside the backend/ folder. This is
# overridable via the DATABASE_URL env var so we can swap in PostgreSQL later.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_SQLITE_PATH = _BACKEND_DIR / "detabeta.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")

# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
# `check_same_thread=False` is a SQLite-only quirk: it lets the connection be
# used across threads, which FastAPI's threadpool needs. It is ignored by other
# databases, so we only add it for SQLite.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

# A factory that produces new Session objects when called.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Base class all ORM models inherit from. SQLAlchemy collects table
    definitions from every subclass of this."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a database session and guarantees it is
    closed afterwards, even if the request raises an error.

    Usage in a route:
        def handler(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
