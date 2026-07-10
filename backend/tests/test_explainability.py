"""
Tests for Engine 8: Explainability.

Strategy: build datasets where we KNOW which feature the model should rely on,
then assert the explanations point at the right feature. This checks the
explanations are meaningful, not just that code runs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.explainability import explain_model


def _informative_classification():
    """
    'signal' cleanly determines the label; 'noise' is random. A good model
    should rely on 'signal', and permutation importance should rank it first.
    """
    rng = np.random.default_rng(0)
    n = 200
    signal = rng.normal(size=n)
    noise = rng.normal(size=n)
    # Label is 1 when signal is positive (with a little randomness).
    label = ((signal + rng.normal(scale=0.2, size=n)) > 0).astype(int)
    return pd.DataFrame(
        {
            "signal": signal + 0.001 * np.arange(n),  # keep continuous, not an ID
            "noise": noise,
            "outcome": label,
        }
    )


def test_report_basic_shape():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=2)
    assert report.model_name, "expected a winning model name"
    assert report.global_importances, "expected global importances"
    assert len(report.examples) == 2, "expected the requested number of examples"


def test_informative_feature_ranks_above_noise():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=1)
    importances = {fi.feature: fi.importance for fi in report.global_importances}
    assert "signal" in importances and "noise" in importances
    # The real signal should matter more to the model than pure noise.
    assert importances["signal"] > importances["noise"]


def test_importances_are_sorted_descending():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=1)
    values = [fi.importance for fi in report.global_importances]
    assert values == sorted(values, reverse=True)


def test_shares_sum_to_about_one():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=1)
    # Shares are computed from positive importances only and should sum to ~1
    # (unless every feature was useless, which is not the case here).
    total_share = sum(fi.share for fi in report.global_importances)
    assert 0.99 <= total_share <= 1.01


def test_local_explanation_has_contributions():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=1)
    ex = report.examples[0]
    assert ex.contributions, "expected per-feature contributions for the row"
    # Contributions must be sorted by absolute effect (biggest driver first).
    effects = [abs(c.effect) for c in ex.contributions]
    assert effects == sorted(effects, reverse=True)
    # Every contribution has a human-readable direction.
    assert all(c.direction in {"increases", "decreases", "no effect"}
               for c in ex.contributions)


def test_regression_target_is_explained():
    """Explainability must also work for a regression target."""
    rng = np.random.default_rng(1)
    n = 200
    size = rng.uniform(50, 200, size=n)
    price = size * 3.0 + rng.normal(scale=5.0, size=n)  # price depends on size
    df = pd.DataFrame({"size": size, "extra": rng.normal(size=n), "price": price})
    report = explain_model(df, target="price", n_examples=2)
    assert report.problem_type == "regression"
    importances = {fi.feature: fi.importance for fi in report.global_importances}
    # 'size' truly drives price, so it should outrank the irrelevant 'extra'.
    assert importances["size"] > importances["extra"]
