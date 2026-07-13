"""
Sessions router: analysis history and re-runs.

Sessions are created and populated implicitly by the analysis endpoints (see
`api/routers/analysis.py`), which call `services.sessions.run_cached`. These
endpoints let the frontend *see* and *manage* that history:

    GET  /api/datasets/{id}/sessions            -- list session history
    GET  /api/datasets/{id}/sessions/active     -- get-or-create the active session
    POST /api/datasets/{id}/sessions/rerun      -- start a fresh session version
    GET  /api/sessions/{session_id}             -- full detail with cached results

"Active" means the newest session for a (dataset, target). Re-running never
deletes anything: it creates a new version, so past analyses stay comparable.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_dataset_or_404
from api.schemas import EngineResultOut, SessionDetailOut, SessionOut
from db import AnalysisSession, Dataset, get_db
from services import sessions

# Two routers: one nested under a dataset, one for a session by id.
# No "/api" prefix: Vercel strips it before forwarding (see vercel.json).
router = APIRouter(prefix="/datasets/{dataset_id}/sessions", tags=["sessions"])
session_router = APIRouter(prefix="/sessions", tags=["sessions"])

_TargetQuery = Query(
    default=None,
    description="Target column to scope sessions to. Omit for the base "
    "(target-independent) session or for the full history.",
)


def _to_summary(db: Session, session: AnalysisSession) -> SessionOut:
    """Build a lightweight session summary (no heavy result payloads)."""
    return SessionOut(
        id=session.id,
        dataset_id=session.dataset_id,
        target=session.target,
        created_at=session.created_at,
        completed_engine_keys=sessions.completed_engine_keys(db, session.id),
    )


@router.get("", response_model=list[SessionOut])
def list_dataset_sessions(
    dataset: Dataset = Depends(get_dataset_or_404),
    target: str | None = _TargetQuery,
    db: Session = Depends(get_db),
) -> list[SessionOut]:
    """List a dataset's analysis sessions, newest first.

    With no target, returns every session. With a target, returns that target's
    sessions plus the shared base session (understand + health).
    """
    found = sessions.list_sessions(db, dataset.id, target=target)
    return [_to_summary(db, s) for s in found]


@router.get("/active", response_model=SessionOut)
def get_active_session(
    dataset: Dataset = Depends(get_dataset_or_404),
    target: str | None = _TargetQuery,
    db: Session = Depends(get_db),
) -> SessionOut:
    """Get (or create) the active session for a (dataset, target)."""
    session = sessions.get_or_create_active_session(db, dataset.id, target)
    return _to_summary(db, session)


@router.post("/rerun", response_model=SessionOut, status_code=201)
def rerun_session(
    dataset: Dataset = Depends(get_dataset_or_404),
    target: str | None = _TargetQuery,
    db: Session = Depends(get_db),
) -> SessionOut:
    """Start a brand-new session version for a (dataset, target).

    The old session is preserved as history. The next analysis calls will
    populate this fresh session's engine results from scratch.
    """
    session = sessions.create_session(db, dataset.id, target)
    return _to_summary(db, session)


@session_router.get("/{session_id}", response_model=SessionDetailOut)
def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
) -> SessionDetailOut:
    """Return a session with the full cached output of every engine that ran."""
    session = db.get(AnalysisSession, session_id)
    if session is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )

    results = [
        EngineResultOut(
            engine_key=r.engine_key,
            status=r.status,
            duration_ms=r.duration_ms,
            error=r.error,
            created_at=r.created_at,
            result=json.loads(r.result_json) if r.result_json else {},
        )
        for r in session.results
    ]
    return SessionDetailOut(
        id=session.id,
        dataset_id=session.dataset_id,
        target=session.target,
        created_at=session.created_at,
        completed_engine_keys=[r.engine_key for r in results if r.status == "completed"],
        results=results,
    )
