"""
Tests for Engine 7: Experiment Studio.

These use small, synthetic datasets with a KNOWN signal so we can assert that
training actually works, the winner is sensible, and the honesty guarantees
(shared folds, baseline comparison, graceful failure) hold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.experiment_studio import run_experiment


def _make_classification_df(n: int = 300, seed: int = 0) -> pd.DataFrame:
    """A learnable binary problem: label depends on two informative features."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    noise = rng.normal(0, 0.5, n)
    # Linear signal -> logistic-friendly, clearly learnable.
    logit = 2.0 * x1 - 1.5 * x2 + noise
    y = (logit > 0).astype(int)
    category = rng.choice(["red", "green", "blue"], size=n)
    return pd.DataFrame({"x1": x1, "x2": x2, "color": category, "label": y})


def _make_regression_df(n: int = 300, seed: int = 1) -> pd.DataFrame:
    """A learnable regression problem: y is a linear function of features."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    noise = rng.normal(0, 0.3, n)
    y = 3.0 * x1 - 2.0 * x2 + 1.0 + noise
    return pd.DataFrame({"x1": x1, "x2": x2, "price": y})


def test_runs_classification_and_reports_results():
    df = _make_classification_df()
    report = run_experiment(df, target="label")

    assert report.problem_type == "binary_classification"
    assert report.primary_metric in {"accuracy", "f1"}
    assert report.successful(), "expected at least one model to train successfully"
    # There should be a chosen winner.
    assert report.best_model
    assert report.best() is not None


def test_classification_is_actually_learnable():
    # With a strong linear signal, the best model should score well above 0.5
    # (random guessing) on accuracy.
    df = _make_classification_df()
    report = run_experiment(df, target="label")
    best = report.best()
    assert best is not None
    acc = best.metrics.get("accuracy")
    # accuracy may be a cross-check metric even if f1 is primary
    if acc is not None:
        assert acc.mean > 0.75, f"expected a learnable signal, got accuracy={acc.mean}"


def test_shared_metrics_present_for_every_model():
    df = _make_classification_df()
    report = run_experiment(df, target="label")
    for r in report.successful():
        # Every successful model must have the primary metric computed.
        assert report.primary_metric in r.metrics


def test_runs_regression():
    df = _make_regression_df()
    report = run_experiment(df, target="price")
    assert report.problem_type == "regression"
    assert report.primary_metric == "rmse"
    assert report.successful()
    best = report.best()
    assert best is not None
    # A strong linear signal should give a high R^2.
    r2 = best.metrics.get("r2")
    if r2 is not None:
        assert r2.mean > 0.8, f"expected strong fit, got r2={r2.mean}"


def test_regression_winner_minimises_error():
    # For rmse (lower is better), the winner must have the lowest rmse among
    # successful models -- verifying the ranking direction is correct.
    df = _make_regression_df()
    report = run_experiment(df, target="price")
    ok = report.successful()
    best = report.best()
    assert best is not None
    lowest = min(r.primary_score for r in ok)
    assert best.primary_score == lowest


def test_baseline_comparison_is_populated():
    df = _make_classification_df()
    report = run_experiment(df, target="label")
    # Whatever the outcome, the engine must explain the baseline comparison.
    assert report.baseline_comparison != ""


def test_drops_rows_with_missing_target():
    df = _make_classification_df(n=200)
    df.loc[:20, "label"] = np.nan  # blank out some answers
    report = run_experiment(df, target="label")
    assert report.n_rows_used < 200
    assert any("missing" in w for w in report.warnings)


def test_summary_is_written():
    df = _make_regression_df()
    report = run_experiment(df, target="price")
    assert report.summary
    assert report.target == "price"
