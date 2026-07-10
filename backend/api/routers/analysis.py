"""
Analysis router: the 9 engine endpoints.

Every endpoint follows the same tiny pattern:
  1. FastAPI loads the dataset's DataFrame via the `load_dataset_df` dependency
     (which handles 404s for a missing dataset or file).
  2. We call the matching function in the analysis service.
  3. We return its JSON-safe dict.

The only variation is whether a `target` query parameter is optional (analysis
half + report) or required (modelling half). A missing/invalid required target
raises TargetError in the service, which we translate into HTTP 400 here.

Example:
    GET /api/datasets/3/analysis/health
    GET /api/datasets/3/analysis/experiment?target=survived
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_dataset_or_404, load_dataset_df
from db import Dataset
from services import analysis
from services.analysis import TargetError

# All analysis endpoints hang off a single dataset.
router = APIRouter(prefix="/api/datasets/{dataset_id}/analysis", tags=["analysis"])

# A reusable optional-target query parameter.
_TargetQuery = Query(
    default=None,
    description="Name of the column to model/relate against. "
    "Required for recommend, experiment, and explain.",
)


def _guard_target(func, *args, **kwargs) -> dict:
    """Run an analysis function, converting TargetError into a clean 400."""
    try:
        return func(*args, **kwargs)
    except TargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Analysis half (Engines 1-5): target optional
# ---------------------------------------------------------------------------

@router.get("/understand")
def understand(df: pd.DataFrame = Depends(load_dataset_df)) -> dict:
    """Engine 1 -- What kind of data is this?"""
    return analysis.understand(df)


@router.get("/health")
def health(df: pd.DataFrame = Depends(load_dataset_df)) -> dict:
    """Engine 2 -- Can I trust this dataset?"""
    return analysis.health(df)


@router.get("/investigate")
def investigate(
    df: pd.DataFrame = Depends(load_dataset_df), target: str | None = _TargetQuery
) -> dict:
    """Engine 3 -- What interesting things exist?"""
    return analysis.investigation(df, target=target)


@router.get("/statistics")
def statistics(
    df: pd.DataFrame = Depends(load_dataset_df), target: str | None = _TargetQuery
) -> dict:
    """Engine 4 -- Are these findings statistically meaningful?"""
    return analysis.statistics(df, target=target)


@router.get("/feature-lab")
def feature_lab(
    df: pd.DataFrame = Depends(load_dataset_df), target: str | None = _TargetQuery
) -> dict:
    """Engine 5 -- How can this data be improved?"""
    return analysis.feature_lab(df, target=target)


# ---------------------------------------------------------------------------
# Modelling half (Engines 6-8): target required
# ---------------------------------------------------------------------------

@router.get("/recommend")
def recommend(
    df: pd.DataFrame = Depends(load_dataset_df), target: str | None = _TargetQuery
) -> dict:
    """Engine 6 -- What should I model, and how?"""
    return _guard_target(analysis.recommendation, df, target=target)


@router.get("/experiment")
def experiment(
    df: pd.DataFrame = Depends(load_dataset_df), target: str | None = _TargetQuery
) -> dict:
    """Engine 7 -- Which model performs best?"""
    return _guard_target(analysis.experiment, df, target=target)


@router.get("/explain")
def explain(
    df: pd.DataFrame = Depends(load_dataset_df), target: str | None = _TargetQuery
) -> dict:
    """Engine 8 -- Why did the model predict this?"""
    return _guard_target(analysis.explain, df, target=target)


# ---------------------------------------------------------------------------
# Capstone (Engine 9): target optional
# ---------------------------------------------------------------------------

@router.get("/report")
def report(
    dataset: Dataset = Depends(get_dataset_or_404),
    df: pd.DataFrame = Depends(load_dataset_df),
    target: str | None = _TargetQuery,
) -> dict:
    """Engine 9 -- What should another human learn from this?"""
    return _guard_target(analysis.report, df, target=target, dataset_name=dataset.name)
