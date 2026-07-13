"""
The sessions service: turns the stateless engines into cached, historical runs.

WHAT A SESSION IS
-----------------
An `AnalysisSession` groups the outputs of the engines for one
(dataset, target) combination. Within a session, each engine's output is cached
as an `EngineResult`, so opening a tab a second time reads from the database
instead of recomputing.

THE THREE RULES (decided with the user)
---------------------------------------
1. Lazy per-engine caching -- an engine runs the first time it is asked for in a
   session, then its result is reused until an explicit refresh.
2. Append-only history -- "re-running" makes a NEW session version; the previous
   one is preserved. The newest session for a (dataset, target) is "active".
3. New session per target -- the target-independent engines (dataset
   understanding + data health) are stored ONCE under the base session
   (`target = None`) and reused across every target-specific session. Picking a
   target uses/creates a distinct session for the target-dependent engines.

This module is the ONLY place that knows how to map an engine key to an engine
function and how the caching behaves. Routers stay thin and just call in here.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import AnalysisSession, Dataset, EngineResult
from services import analysis
from services.analysis import TargetError


class TargetMode(str, Enum):
    """How a given engine relates to the target column.

    * INDEPENDENT -- ignores the target entirely (dataset understanding, health).
                     Always cached under the base session (target = None).
    * OPTIONAL    -- uses the target when present, works without it.
    * REQUIRED    -- cannot run without a valid target.
    """

    INDEPENDENT = "independent"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass(frozen=True)
class EngineSpec:
    """Everything the service needs to know to run one engine by key."""

    key: str
    mode: TargetMode
    # A normalized callable: (df, target, dataset_name) -> JSON-safe dict.
    run: Callable[[pd.DataFrame, str | None, str], dict]


# ---------------------------------------------------------------------------
# The dispatch table: engine_key -> how to run it.
# Wrapping each analysis function in a uniform (df, target, dataset_name)
# signature keeps `run_cached` below completely generic.
# ---------------------------------------------------------------------------
ENGINES: dict[str, EngineSpec] = {
    "understand": EngineSpec(
        "understand", TargetMode.INDEPENDENT, lambda df, target, name: analysis.understand(df)
    ),
    "health": EngineSpec(
        "health", TargetMode.INDEPENDENT, lambda df, target, name: analysis.health(df)
    ),
    "investigate": EngineSpec(
        "investigate", TargetMode.OPTIONAL, lambda df, target, name: analysis.investigation(df, target=target)
    ),
    "statistics": EngineSpec(
        "statistics", TargetMode.OPTIONAL, lambda df, target, name: analysis.statistics(df, target=target)
    ),
    "feature-lab": EngineSpec(
        "feature-lab", TargetMode.OPTIONAL, lambda df, target, name: analysis.feature_lab(df, target=target)
    ),
    "recommend": EngineSpec(
        "recommend", TargetMode.REQUIRED, lambda df, target, name: analysis.recommendation(df, target=target)
    ),
    "experiment": EngineSpec(
        "experiment", TargetMode.REQUIRED, lambda df, target, name: analysis.experiment(df, target=target)
    ),
    "explain": EngineSpec(
        "explain", TargetMode.REQUIRED, lambda df, target, name: analysis.explain(df, target=target)
    ),
    "report": EngineSpec(
        "report", TargetMode.OPTIONAL, lambda df, target, name: analysis.report(df, target=target, dataset_name=name)
    ),
}


class UnknownEngineError(ValueError):
    """Raised when an engine key is not in the dispatch table."""


def get_engine_spec(engine_key: str) -> EngineSpec:
    """Look up an engine by key or raise a clear error."""
    spec = ENGINES.get(engine_key)
    if spec is None:
        known = ", ".join(sorted(ENGINES))
        raise UnknownEngineError(f"Unknown engine '{engine_key}'. Known engines: {known}.")
    return spec


# ---------------------------------------------------------------------------
# Target normalization
# ---------------------------------------------------------------------------

def _normalize_target(target: str | None) -> str | None:
    """Treat empty strings as 'no target' so sessions key consistently."""
    if target is None:
        return None
    target = target.strip()
    return target or None


def _effective_target(spec: EngineSpec, target: str | None) -> str | None:
    """The target a given engine is actually stored under.

    Target-independent engines always live in the base (target = None) session,
    no matter what target the caller passed. Everything else uses the caller's
    (normalized) target.
    """
    if spec.mode is TargetMode.INDEPENDENT:
        return None
    return _normalize_target(target)


# ---------------------------------------------------------------------------
# Session lookup / creation
# ---------------------------------------------------------------------------

def get_active_session(
    db: Session, dataset_id: int, target: str | None
) -> AnalysisSession | None:
    """Return the newest session for a (dataset, target), or None if none exist."""
    target = _normalize_target(target)
    stmt = (
        select(AnalysisSession)
        .where(
            AnalysisSession.dataset_id == dataset_id,
            AnalysisSession.target.is_(None) if target is None else AnalysisSession.target == target,
        )
        .order_by(AnalysisSession.created_at.desc(), AnalysisSession.id.desc())
    )
    return db.execute(stmt).scalars().first()


def create_session(db: Session, dataset_id: int, target: str | None) -> AnalysisSession:
    """Always create a brand-new session version for a (dataset, target)."""
    session = AnalysisSession(dataset_id=dataset_id, target=_normalize_target(target))
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_or_create_active_session(
    db: Session, dataset_id: int, target: str | None
) -> AnalysisSession:
    """Return the active session for a (dataset, target), creating one if needed."""
    session = get_active_session(db, dataset_id, target)
    if session is None:
        session = create_session(db, dataset_id, target)
    return session


def list_sessions(
    db: Session, dataset_id: int, target: str | None = None, include_base: bool = True
) -> list[AnalysisSession]:
    """List a dataset's sessions, newest first.

    * target is None            -> every session for the dataset.
    * target given, include_base-> that target's sessions plus the base session.
    * target given, no base     -> only that target's sessions.
    """
    conditions = [AnalysisSession.dataset_id == dataset_id]
    target = _normalize_target(target)
    if target is not None:
        if include_base:
            conditions.append(
                (AnalysisSession.target == target) | (AnalysisSession.target.is_(None))
            )
        else:
            conditions.append(AnalysisSession.target == target)
    stmt = (
        select(AnalysisSession)
        .where(*conditions)
        .order_by(AnalysisSession.created_at.desc(), AnalysisSession.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Cached engine results
# ---------------------------------------------------------------------------

def _find_result(db: Session, session_id: int, engine_key: str) -> EngineResult | None:
    stmt = select(EngineResult).where(
        EngineResult.session_id == session_id,
        EngineResult.engine_key == engine_key,
    )
    return db.execute(stmt).scalars().first()


@dataclass
class RunOutcome:
    """What `run_cached` hands back to the router."""

    result: dict
    session_id: int
    engine_key: str
    cached: bool
    status: str
    duration_ms: int | None
    error: str | None

    def as_meta(self) -> dict:
        """Lightweight cache metadata (no heavy result payload)."""
        return {
            "session_id": self.session_id,
            "engine_key": self.engine_key,
            "cached": self.cached,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }


def run_cached(
    db: Session,
    dataset: Dataset,
    df: pd.DataFrame,
    engine_key: str,
    target: str | None = None,
    refresh: bool = False,
) -> RunOutcome:
    """Run an engine, using the session cache unless `refresh` is requested.

    Steps:
      1. Resolve the engine spec and the target it is actually stored under
         (target-independent engines collapse to the base session).
      2. Get-or-create the active session for that effective target.
      3. If a completed result is cached and not refreshing, return it.
      4. Otherwise run the engine (timed), persist the outcome, and return it.

    A missing/invalid REQUIRED target still raises TargetError so the router can
    map it to HTTP 400 -- and we deliberately do NOT cache that failure, since it
    is a bad request rather than an engine result.
    """
    spec = get_engine_spec(engine_key)
    effective_target = _effective_target(spec, target)
    session = get_or_create_active_session(db, dataset.id, effective_target)

    existing = _find_result(db, session.id, engine_key)
    if existing is not None and existing.status == "completed" and not refresh:
        return RunOutcome(
            result=json.loads(existing.result_json or "{}"),
            session_id=session.id,
            engine_key=engine_key,
            cached=True,
            status=existing.status,
            duration_ms=existing.duration_ms,
            error=None,
        )

    # Run the engine fresh. TargetError propagates (not cached) -> 400 upstream.
    started = time.perf_counter()
    try:
        result = spec.run(df, target, dataset.name)
    except TargetError:
        raise
    duration_ms = int((time.perf_counter() - started) * 1000)

    result_json = json.dumps(result)

    # Upsert: overwrite the existing row (e.g. on refresh) or insert a new one.
    if existing is not None:
        existing.status = "completed"
        existing.result_json = result_json
        existing.error = None
        existing.duration_ms = duration_ms
    else:
        db.add(
            EngineResult(
                session_id=session.id,
                engine_key=engine_key,
                status="completed",
                result_json=result_json,
                error=None,
                duration_ms=duration_ms,
            )
        )
    db.commit()

    return RunOutcome(
        result=result,
        session_id=session.id,
        engine_key=engine_key,
        cached=False,
        status="completed",
        duration_ms=duration_ms,
        error=None,
    )


def completed_engine_keys(db: Session, session_id: int) -> list[str]:
    """Which engines are cached (completed) in a session -- for history display."""
    stmt = (
        select(EngineResult.engine_key)
        .where(
            EngineResult.session_id == session_id,
            EngineResult.status == "completed",
        )
        .order_by(EngineResult.created_at)
    )
    return list(db.execute(stmt).scalars().all())
