"""
Database models: the shape of what we store.

WHAT WE PERSIST
---------------
  * Project         -- a workspace/folder that groups related work.
  * Dataset         -- one uploaded CSV file that belongs to a project.
  * AnalysisSession -- one "run" over a dataset for a given target column.
  * EngineResult    -- a single engine's cached output within a session.

WHY SESSIONS AND CACHED RESULTS?
--------------------------------
The engines are still pure functions, but recomputing them on every request is
wasteful and throws away useful history. A *session* groups the results of the
engines for one (dataset, target) combination:

  * Speed             -- each engine runs once per session, then is read from the
                         DB instantly on later visits ("lazy per-engine caching").
  * History           -- sessions are append-only. A "re-run" creates a new
                         session version; the old one is preserved so past
                         analyses can be listed and compared.
  * Improvement track -- re-running after cleaning produces a new session, so
                         health/metrics changes over time become visible.

The raw CSV still lives on disk; sessions only store the engines' JSON output.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp. Stored on every row for ordering/history."""
    return datetime.now(timezone.utc)


class Project(Base):
    """A workspace that groups datasets together (e.g. 'Titanic study')."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Provider-scoped user ID from the JWT ``sub`` claim. Nullable only so
    # pre-auth rows can be retained until an explicit ownership migration;
    # application routes never expose unowned rows.
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # One project has many datasets. `cascade="all, delete-orphan"` means
    # deleting a project also deletes its datasets (and their files, which we
    # handle in the service layer).
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Dataset.created_at",
    )


class Dataset(Base):
    """One uploaded CSV file belonging to a project.

    We store *metadata* here (name, shape, where the file lives on disk), never
    the raw table contents. The actual CSV sits in the storage folder and is
    loaded into a pandas DataFrame only when an analysis runs.
    """

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-facing name (original uploaded filename, e.g. "passengers.csv").
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Relative path inside the storage folder, e.g. "3/passengers.csv".
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Cached shape so the UI can show "20 rows x 8 columns" without re-reading
    # the file. These are cheap facts, not analysis results.
    n_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_columns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="datasets")

    # Deleting a dataset removes all of its analysis sessions (and their cached
    # engine results, which cascade from the session).
    sessions: Mapped[list["AnalysisSession"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="AnalysisSession.created_at",
    )


class AnalysisSession(Base):
    """One analysis "run" over a dataset for a given target column.

    A session is the container for cached engine outputs. There can be many
    sessions per (dataset, target) pair -- that is the version history. The
    newest one for a (dataset, target) is treated as the "active" session; older
    ones are kept so past analyses can be listed and compared.

    ``target`` is nullable on purpose:
      * NULL          -> the "base" session holding target-independent engines
                         (dataset understanding, data health). Computed once and
                         reused across every target-specific session.
      * a column name -> a session for the target-dependent engines (ML
                         recommendation, experiment studio, explainability, ...).
    """

    __tablename__ = "analysis_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # None = target-independent base session; otherwise the chosen target column.
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="sessions")

    # One cached row per engine per session (enforced below).
    results: Mapped[list["EngineResult"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="EngineResult.created_at",
    )


class EngineResult(Base):
    """A single engine's cached output inside a session.

    ``result_json`` holds the JSON-safe dict the engine produced (already run
    through the serialization service), stored as a text blob. We keep it as
    text rather than a JSON column so the models stay portable across SQLite and
    Postgres without extra type handling.
    """

    __tablename__ = "engine_results"
    __table_args__ = (
        # A given engine is cached at most once per session; re-running an engine
        # updates this row (or a new session is created for a fresh version).
        UniqueConstraint("session_id", "engine_key", name="uq_engine_per_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Which engine produced this, e.g. "understand", "health", "experiment".
    engine_key: Mapped[str] = mapped_column(String(50), nullable=False)
    # "completed" when the engine returned output, "failed" when it raised.
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    # JSON-encoded engine output (empty string when the run failed).
    result_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Human-readable error message when status == "failed".
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # How long the engine took, in milliseconds (None if unknown).
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    session: Mapped["AnalysisSession"] = relationship(back_populates="results")
