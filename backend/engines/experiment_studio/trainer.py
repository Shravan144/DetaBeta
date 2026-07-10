"""
Model training + honest scoring for Engine 7 (Experiment Studio).

This module turns Engine 6's abstract algorithm suggestions (which carry a
`sklearn_path` string like "sklearn.ensemble.RandomForestClassifier") into real
scikit-learn estimators, wraps each in the leak-free preprocessing pipeline, and
evaluates it with cross-validation.

Key honesty guarantees:
  - every model is scored on the SAME cross-validation folds (fair comparison)
  - preprocessing is re-fit per fold inside the pipeline (no leakage)
  - we report both the mean score AND its std across folds (stability signal)
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import KFold, StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.tree import (
    DecisionTreeClassifier,
    DecisionTreeRegressor,
)

from .preprocessing import build_preprocessor

# --------------------------------------------------------------------------- #
# Map Engine 6's sklearn_path strings to real estimator classes.
# We keep this explicit (rather than dynamic import) so it is safe and readable.
# --------------------------------------------------------------------------- #
_ESTIMATORS: dict[str, type] = {
    "sklearn.linear_model.LogisticRegression": LogisticRegression,
    "sklearn.tree.DecisionTreeClassifier": DecisionTreeClassifier,
    "sklearn.ensemble.RandomForestClassifier": RandomForestClassifier,
    "sklearn.ensemble.GradientBoostingClassifier": GradientBoostingClassifier,
    "sklearn.linear_model.LinearRegression": LinearRegression,
    "sklearn.tree.DecisionTreeRegressor": DecisionTreeRegressor,
    "sklearn.ensemble.RandomForestRegressor": RandomForestRegressor,
    "sklearn.ensemble.GradientBoostingRegressor": GradientBoostingRegressor,
}

# Algorithms that need feature scaling to behave well. Tree-based models are
# scale-invariant, so we skip scaling for them (faster and cleaner).
_NEEDS_SCALING = {
    "sklearn.linear_model.LogisticRegression",
    "sklearn.linear_model.LinearRegression",
}

# scikit-learn scoring names keyed by our metric names. For error metrics we use
# the "neg_" scorers (sklearn maximises, so it negates errors); we flip the sign
# back when reporting so users see a normal positive RMSE/MAE.
_CLASSIFICATION_SCORERS = {
    "accuracy": "accuracy",
    "f1": "f1_weighted",
    "roc_auc": "roc_auc",
    "precision": "precision_weighted",
    "recall": "recall_weighted",
}
_REGRESSION_SCORERS = {
    "rmse": "neg_root_mean_squared_error",
    "mae": "neg_neg_placeholder",  # replaced below; kept for clarity
    "r2": "r2",
}
_REGRESSION_SCORERS["mae"] = "neg_mean_absolute_error"

# Metrics where a LOWER value is better (errors). Everything else: higher better.
_LOWER_IS_BETTER = {"rmse", "mae"}


def build_estimator(sklearn_path: str, problem_type: str):
    """
    Instantiate a scikit-learn estimator from Engine 6's path string.

    Returns None if we don't recognise the path (the caller records a failure
    and moves on rather than crashing the whole experiment).
    """
    cls = _ESTIMATORS.get(sklearn_path)
    if cls is None:
        return None

    # Sensible, beginner-friendly defaults. random_state makes runs reproducible.
    kwargs: dict = {}
    if sklearn_path == "sklearn.linear_model.LogisticRegression":
        kwargs = {"max_iter": 1000}
    if "random" in sklearn_path.lower() or "GradientBoosting" in sklearn_path:
        kwargs["random_state"] = 42
    if "DecisionTree" in sklearn_path:
        kwargs["random_state"] = 42

    return cls(**kwargs)


def needs_scaling(sklearn_path: str) -> bool:
    """Whether this algorithm benefits from standard-scaled numeric inputs."""
    return sklearn_path in _NEEDS_SCALING


def make_cv(problem_type: str, n_folds: int, stratify: bool, y: pd.Series):
    """
    Build the cross-validation splitter, shared identically across all models.

    We cap folds so we never ask for more folds than the smallest class can
    support (a common crash on small/imbalanced data).
    """
    is_classification = "classification" in problem_type

    # Never use more folds than the rarest class has members.
    max_folds = n_folds
    if is_classification:
        min_class = int(y.value_counts().min())
        max_folds = max(2, min(n_folds, min_class))
    else:
        max_folds = max(2, min(n_folds, len(y)))

    if is_classification and stratify:
        return StratifiedKFold(n_splits=max_folds, shuffle=True, random_state=42), max_folds
    return KFold(n_splits=max_folds, shuffle=True, random_state=42), max_folds


def scorers_for(problem_type: str, metric_names: list[str]) -> dict[str, str]:
    """Translate our metric names into scikit-learn scoring strings."""
    is_classification = "classification" in problem_type
    table = _CLASSIFICATION_SCORERS if is_classification else _REGRESSION_SCORERS
    out: dict[str, str] = {}
    for name in metric_names:
        if name in table:
            out[name] = table[name]
    return out


def evaluate_model(
    estimator,
    preprocessor,
    X: pd.DataFrame,
    y: pd.Series,
    cv,
    scoring: dict[str, str],
) -> tuple[dict[str, tuple[float, float]], float]:
    """
    Run cross-validation for one model and return metric -> (mean, std) plus the
    wall-clock training time.

    The estimator is wrapped with the preprocessor in a single Pipeline so that
    all preprocessing is fit only on each fold's training portion.
    """
    pipe = Pipeline([("prep", preprocessor), ("model", estimator)])

    start = time.perf_counter()
    cv_results = cross_validate(
        pipe,
        X,
        y,
        cv=cv,
        scoring=scoring,
        error_score="raise",
        n_jobs=None,
    )
    elapsed = time.perf_counter() - start

    metrics: dict[str, tuple[float, float]] = {}
    for metric_name in scoring:
        raw = cv_results[f"test_{metric_name}"]
        # Flip sign for the "neg_" error scorers so we report positive errors.
        if metric_name in _LOWER_IS_BETTER:
            raw = -raw
        metrics[metric_name] = (float(np.mean(raw)), float(np.std(raw)))

    return metrics, elapsed
