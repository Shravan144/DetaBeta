"""
The analysis service: the bridge between the web layer and the 9 engines.

WHY THIS LAYER EXISTS
---------------------
Routes should stay thin. They deal with HTTP: parsing requests, status codes,
JSON. They should NOT know how to call an engine, in what order, or how to
reuse work between engines. All of that lives here.

Each public function below wraps exactly one engine and returns a JSON-safe
dict (already run through `to_jsonable`). A route can therefore do:

    result = analysis.health(df)
    return result

...and never touch the engines directly.

A NOTE ON EFFICIENCY (a real data-science lesson)
-------------------------------------------------
Engine 1 (`understand_dataset`) profiles every column and several later engines
need that profile. Rather than recompute it inside each engine, we compute it
ONCE here and pass it in where the engine accepts it. Same answer, less work.
"""

from __future__ import annotations

import pandas as pd

from engines.data_health import assess_health
from engines.dataset_understanding import understand_dataset
from engines.experiment_studio import run_experiment
from engines.explainability import explain_model
from engines.feature_lab import recommend_features
from engines.investigation import investigate
from engines.ml_recommendation import recommend_model
from engines.report import generate_report
from engines.statistics import analyze_significance
from services.serialization import to_jsonable


class TargetError(ValueError):
    """Raised when a target column is required but missing or not in the data.

    The route layer catches this and turns it into a clean HTTP 400 rather than
    a 500 server error, so the user gets a helpful message.
    """


def _require_target(df: pd.DataFrame, target: str | None) -> str:
    """Validate that `target` is provided and actually exists in the data."""
    if not target:
        raise TargetError("A 'target' column is required for this analysis.")
    if target not in df.columns:
        raise TargetError(
            f"Target column '{target}' is not in the dataset. "
            f"Available columns: {', '.join(map(str, df.columns))}."
        )
    return target


# ---------------------------------------------------------------------------
# Analysis half (Engines 1-5) -- a target is optional.
# ---------------------------------------------------------------------------

def understand(df: pd.DataFrame) -> dict:
    """Engine 1 -- What kind of data is this?"""
    return to_jsonable(understand_dataset(df))


def health(df: pd.DataFrame) -> dict:
    """Engine 2 -- Can I trust this dataset?"""
    profile = understand_dataset(df)
    return to_jsonable(assess_health(df, profile))


def investigation(df: pd.DataFrame, target: str | None = None) -> dict:
    """Engine 3 -- What interesting things exist?"""
    profile = understand_dataset(df)
    return to_jsonable(investigate(df, profile, target=target))


def statistics(df: pd.DataFrame, target: str | None = None) -> dict:
    """Engine 4 -- Are these findings statistically meaningful?"""
    profile = understand_dataset(df)
    invest = investigate(df, profile, target=target)
    return to_jsonable(analyze_significance(df, profile, invest, target=target))


def feature_lab(df: pd.DataFrame, target: str | None = None) -> dict:
    """Engine 5 -- How can this data be improved?"""
    profile = understand_dataset(df)
    return to_jsonable(recommend_features(df, profile, target=target))


# ---------------------------------------------------------------------------
# Modelling half (Engines 6-8) -- a target is REQUIRED.
# ---------------------------------------------------------------------------

def recommendation(df: pd.DataFrame, target: str | None = None) -> dict:
    """Engine 6 -- What should I model, and how?"""
    tgt = _require_target(df, target)
    profile = understand_dataset(df)
    return to_jsonable(recommend_model(profile, target=tgt, raw_df=df))


def experiment(df: pd.DataFrame, target: str | None = None) -> dict:
    """Engine 7 -- Which model performs best?"""
    tgt = _require_target(df, target)
    return to_jsonable(run_experiment(df, target=tgt))


def explain(df: pd.DataFrame, target: str | None = None) -> dict:
    """Engine 8 -- Why did the model predict this?"""
    tgt = _require_target(df, target)
    return to_jsonable(explain_model(df, target=tgt))


# ---------------------------------------------------------------------------
# Capstone (Engine 9) -- a target is optional; modelling sections only appear
# when a valid target is supplied.
# ---------------------------------------------------------------------------

def report(df: pd.DataFrame, target: str | None = None, dataset_name: str = "dataset") -> dict:
    """Engine 9 -- What should another human learn from this?"""
    # If a target was given, make sure it's valid; otherwise the report simply
    # omits the modelling half rather than failing.
    if target:
        _require_target(df, target)
    return to_jsonable(generate_report(df, target=target, dataset_name=dataset_name))
