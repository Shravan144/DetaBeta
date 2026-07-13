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
import tempfile
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Where is the database?
# ---------------------------------------------------------------------------
# Priority order:
#   1. DATABASE_URL_UNPOOLED  -- Neon's *direct* endpoint. Preferred because we
#      let SQLAlchemy manage its own connection pool; stacking that on top of
#      Neon's PgBouncer pooler can trip up psycopg v3's prepared statements.
#   2. DATABASE_URL           -- any Postgres URL (Neon's pooled endpoint, etc).
#   3. SQLite file in the temp dir -- the zero-setup local/dev fallback. We use
#      /tmp because that is reliably writable under `vercel dev` and serverless.
_DEFAULT_SQLITE_PATH = Path(tempfile.gettempdir()) / "detabeta.db"


def _resolve_database_url() -> str:
    """Pick the best available database URL and normalize it for SQLAlchemy.

    Neon (and some hosts) hand out URLs like `postgres://...` or
    `postgresql://...`. SQLAlchemy needs an explicit driver, and we install
    psycopg v3, so we rewrite the scheme to `postgresql+psycopg://`. We also
    make sure TLS is requested, which Neon requires.
    """
    raw = (
        os.environ.get("DATABASE_URL_UNPOOLED")
        or os.environ.get("DATABASE_URL")
        or f"sqlite:///{_DEFAULT_SQLITE_PATH}"
    )

    if raw.startswith("sqlite"):
        return raw

    # Normalize the scheme to the psycopg v3 driver.
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    # (If it already specifies a +driver, e.g. postgresql+psycopg://, leave it.)

    # Ensure TLS is on (Neon rejects non-SSL connections).
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"

    return raw


DATABASE_URL = _resolve_database_url()
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
# `check_same_thread=False` is a SQLite-only quirk: it lets the connection be
# used across threads, which FastAPI's threadpool needs. It is ignored by other
# databases, so we only add it for SQLite.
_connect_args = {"check_same_thread": False} if _IS_SQLITE else {}

# For Postgres/Neon we enable `pool_pre_ping`: Neon's compute suspends when idle
# and drops connections, so we check a connection is still alive before using it
# (this transparently reconnects instead of raising a stale-connection error).
_engine_kwargs: dict = {"connect_args": _connect_args, "future": True}
if not _IS_SQLITE:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **_engine_kwargs)

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
