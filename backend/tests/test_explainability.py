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


# --------------------------------------------------------------------------- #
# SHAP / Shapley-value local explanations
# --------------------------------------------------------------------------- #
def test_local_explanations_use_shapley():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=1)
    assert report.examples[0].method == "shapley"


def test_shapley_efficiency_property_classification():
    """
    The defining property of Shapley values: baseline + sum(contributions)
    must equal the model's actual prediction. We compute the baseline as the
    mean prediction over the sampled references, so this holds (near) exactly.
    """
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=2)
    for ex in report.examples:
        total = sum(c.effect for c in ex.contributions)
        assert ex.baseline_prediction is not None
        reconstructed = ex.baseline_prediction + total
        # For classification the prediction target is the positive-class prob.
        assert abs(reconstructed - ex.predicted_probability) < 1e-6


def test_shapley_efficiency_property_regression():
    rng = np.random.default_rng(2)
    n = 200
    size = rng.uniform(50, 200, size=n)
    price = size * 3.0 + rng.normal(scale=5.0, size=n)
    df = pd.DataFrame({"size": size, "extra": rng.normal(size=n), "price": price})
    report = explain_model(df, target="price", n_examples=2)
    for ex in report.examples:
        total = sum(c.effect for c in ex.contributions)
        reconstructed = ex.baseline_prediction + total
        # predicted_label is the regression value here.
        assert abs(reconstructed - float(ex.predicted_label)) < 1e-6


def test_shapley_credits_the_informative_feature():
    """The row's biggest Shapley driver should be the informative feature."""
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=3)
    # Across example rows, 'signal' should dominate 'noise' on average.
    signal_total = 0.0
    noise_total = 0.0
    for ex in report.examples:
        for c in ex.contributions:
            if c.feature == "signal":
                signal_total += abs(c.effect)
            elif c.feature == "noise":
                noise_total += abs(c.effect)
    assert signal_total > noise_total


# --------------------------------------------------------------------------- #
# Confusion matrix
# --------------------------------------------------------------------------- #
def test_binary_confusion_matrix_is_populated():
    df = _informative_classification()
    report = explain_model(df, target="outcome", n_examples=1)
    cm = report.confusion
    assert cm is not None and cm.is_binary
    # The four quadrants must be real integers that account for every row.
    quad_sum = cm.true_negative + cm.false_positive + cm.false_negative + cm.true_positive
    assert quad_sum == cm.n_samples
    # Accuracy equals the correct predictions (the diagonal) over the total.
    correct = cm.true_negative + cm.true_positive
    assert abs(cm.accuracy - correct / cm.n_samples) < 1e-9


def test_regression_has_no_confusion_matrix():
    rng = np.random.default_rng(3)
    n = 150
    size = rng.uniform(50, 200, size=n)
    price = size * 2.0 + rng.normal(scale=5.0, size=n)
    df = pd.DataFrame({"size": size, "price": price})
    report = explain_model(df, target="price", n_examples=1)
    assert report.confusion is None


def test_multiclass_confusion_matrix_matches_labels():
    rng = np.random.default_rng(4)
    n = 240
    x = rng.normal(size=n)
    # Three classes carved out of a continuous signal.
    cls = np.select([x < -0.5, x > 0.5], ["low", "high"], default="mid")
    df = pd.DataFrame({"driver": x, "junk": rng.normal(size=n), "grade": cls})
    report = explain_model(df, target="grade", n_examples=1)
    cm = report.confusion
    assert cm is not None and not cm.is_binary
    assert len(cm.matrix) == len(cm.labels)
    assert all(len(row) == len(cm.labels) for row in cm.matrix)
    assert sum(sum(row) for row in cm.matrix) == cm.n_samples
