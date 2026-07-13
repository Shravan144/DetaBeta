"""
Analysis router: the 9 engine endpoints (now session-cached).

Every endpoint follows the same tiny pattern:
  1. FastAPI loads the dataset (`get_dataset_or_404`) and its DataFrame
     (`load_dataset_df`), plus a DB session (`get_db`).
  2. We delegate to `services.sessions.run_cached`, which finds or creates the
     active analysis session for this (dataset, target), returns a cached engine
     result if one exists, or runs the engine fresh and stores it.
  3. We return the engine's JSON-safe dict -- exactly as before, so the frontend
     contract is unchanged.

Cache metadata (was this served from cache? which session? how long did it
take?) is attached as response headers so callers can surface it without the
response body shape changing:
    X-DetaBeta-Cached:     "true" | "false"
    X-DetaBeta-Session-Id: <int>
    X-DetaBeta-Duration-Ms:<int>

A `refresh=true` query parameter forces the engine to recompute and overwrite
its cached result. A missing/invalid required target still raises TargetError,
which we translate into HTTP 400.

Example:
    GET /api/datasets/3/analysis/health
    GET /api/datasets/3/analysis/experiment?target=survived
    GET /api/datasets/3/analysis/experiment?target=survived&refresh=true
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from api.deps import get_dataset_or_404, load_dataset_df
from db import Dataset, get_db
from services import report_export, sessions
from services.analysis import TargetError

# All analysis endpoints hang off a single dataset.
# No "/api" prefix: Vercel strips it before forwarding (see vercel.json).
router = APIRouter(prefix="/datasets/{dataset_id}/analysis", tags=["analysis"])

# A reusable optional-target query parameter.
_TargetQuery = Query(
    default=None,
    description="Name of the column to model/relate against. "
    "Required for recommend, experiment, and explain.",
)

# Whether to bypass the cache and recompute this engine.
_RefreshQuery = Query(
    default=False,
    description="Set true to recompute and overwrite the cached result.",
)


def _run(
    response: Response,
    db: Session,
    dataset: Dataset,
    df: pd.DataFrame,
    engine_key: str,
    target: str | None,
    refresh: bool,
) -> dict:
    """Run an engine through the session cache and attach cache-info headers.

    TargetError (missing/invalid required target) becomes a clean HTTP 400.
    """
    try:
        outcome = sessions.run_cached(
            db, dataset, df, engine_key, target=target, refresh=refresh
        )
    except TargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    response.headers["X-DetaBeta-Cached"] = "true" if outcome.cached else "false"
    response.headers["X-DetaBeta-Session-Id"] = str(outcome.session_id)
    if outcome.duration_ms is not None:
        response.headers["X-DetaBeta-Duration-Ms"] = str(outcome.duration_ms)
    return outcome.result


# ---------------------------------------------------------------------------
# Analysis half (Engines 1-5): target optional
# ---------------------------------------------------------------------------

@router.get("/understand")
def understand(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 1 -- What kind of data is this?"""
    return _run(response, db, dataset, df, "understand", None, refresh)


@router.get("/health")
def health(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 2 -- Can I trust this dataset?"""
    return _run(response, db, dataset, df, "health", None, refresh)


@router.get("/investigate")
def investigate(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 3 -- What interesting things exist?"""
    return _run(response, db, dataset, df, "investigate", target, refresh)


@router.get("/statistics")
def statistics(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 4 -- Are these findings statistically meaningful?"""
    return _run(response, db, dataset, df, "statistics", target, refresh)


@router.get("/feature-lab")
def feature_lab(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 5 -- How can this data be improved?"""
    return _run(response, db, dataset, df, "feature-lab", target, refresh)


# ---------------------------------------------------------------------------
# Modelling half (Engines 6-8): target required
# ---------------------------------------------------------------------------

@router.get("/recommend")
def recommend(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 6 -- What should I model, and how?"""
    return _run(response, db, dataset, df, "recommend", target, refresh)


@router.get("/experiment")
def experiment(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 7 -- Which model performs best?"""
    return _run(response, db, dataset, df, "experiment", target, refresh)


@router.get("/explain")
def explain(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 8 -- Why did the model predict this?"""
    return _run(response, db, dataset, df, "explain", target, refresh)


# ---------------------------------------------------------------------------
# Capstone (Engine 9): target optional
# ---------------------------------------------------------------------------

@router.get("/report")
def report(
    response: Response,
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    refresh: bool = _RefreshQuery,
    db: Session = Depends(get_db),
) -> dict:
    """Engine 9 -- What should another human learn from this?"""
    return _run(response, db, dataset, df, "report", target, refresh)


@router.get("/report/export")
def report_export_endpoint(
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
    format: str = Query(
        default="html",
        description="Export format: 'html' (self-contained file), "
        "'print' (auto-prints for Save-as-PDF), or 'md' (Markdown).",
    ),
    db: Session = Depends(get_db),
):
    """Export Engine 9's report as a downloadable HTML / PDF-ready / Markdown file.

    The report itself is pulled through the session cache (`run_cached`), so
    exporting reuses the already-composed narrative instead of recomputing it.
    We then convert that dict to the requested document format.

    * html  -> downloads a self-contained .html file.
    * print -> returns an HTML page that opens the browser print dialog, which
               the user saves as PDF (no server-side PDF library needed).
    * md    -> downloads a .md file.
    """
    fmt = (format or "html").lower()
    spec = report_export.FORMATS.get(fmt)
    if spec is None:
        known = ", ".join(sorted(report_export.FORMATS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown export format '{format}'. Supported: {known}.",
        )

    builder, media_type, extension, as_attachment = spec

    try:
        outcome = sessions.run_cached(db, dataset, df, "report", target=target)
    except TargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    content = builder(outcome.result)
    headers = {}
    if as_attachment:
        filename = report_export.safe_filename(dataset.name, extension)
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    response_cls = PlainTextResponse if fmt == "md" else HTMLResponse
    return response_cls(content=content, media_type=media_type, headers=headers)
