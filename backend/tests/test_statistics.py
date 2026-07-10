"""
Tests for Engine 4 (Statistics).

We build datasets where we KNOW the right answer, then check the engine reaches
it: a real effect should come back significant with a sizable effect size, and
pure noise should come back not significant.
"""

import numpy as np
import pandas as pd
import pytest

from engines.statistics import analyze_significance
from engines.statistics.tests import (
    chi_square_test,
    correlation_test,
    group_difference_test,
)
from engines.statistics.types import EffectSize, Significance, TestKind


# --------------------------------------------------------------------------- #
# Correlation test
# --------------------------------------------------------------------------- #
def test_correlation_detects_real_relationship():
    rng = np.random.default_rng(0)
    x = np.linspace(0, 10, 100) + 0.5
    y = 2.0 * x + rng.normal(0, 1.0, size=100)  # strong but noisy linear link
    df = pd.DataFrame({"x": x, "y": y})

    result = correlation_test(df, "x", "y")
    assert result.significance == Significance.SIGNIFICANT
    assert result.p_value < 0.05
    assert result.effect_size == EffectSize.LARGE
    assert result.effect_value > 0.8


def test_correlation_rejects_noise():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {"a": rng.normal(size=100) + 0.5, "b": rng.normal(size=100) + 0.5}
    )
    result = correlation_test(df, "a", "b")
    # Two independent random columns should not be significantly correlated.
    assert result.significance == Significance.NOT_SIGNIFICANT


def test_correlation_inconclusive_when_too_few_rows():
    df = pd.DataFrame({"a": [1.5, 2.5, 3.5], "b": [2.5, 4.5, 6.5]})
    result = correlation_test(df, "a", "b")
    assert result.significance == Significance.INCONCLUSIVE


# --------------------------------------------------------------------------- #
# Group difference: t-test (2 groups)
# --------------------------------------------------------------------------- #
def test_ttest_detects_group_gap():
    rng = np.random.default_rng(2)
    group_a = rng.normal(10, 2, size=40)
    group_b = rng.normal(15, 2, size=40)  # clearly higher mean
    df = pd.DataFrame(
        {
            "value": np.concatenate([group_a, group_b]),
            "grp": ["a"] * 40 + ["b"] * 40,
        }
    )
    result = group_difference_test(df, "value", "grp")
    assert result.test_kind == TestKind.T_TEST
    assert result.significance == Significance.SIGNIFICANT
    assert result.effect_size in (EffectSize.MEDIUM, EffectSize.LARGE)


def test_ttest_no_gap_when_same_distribution():
    rng = np.random.default_rng(3)
    vals = rng.normal(10, 2, size=80)
    df = pd.DataFrame({"value": vals, "grp": (["a"] * 40) + (["b"] * 40)})
    result = group_difference_test(df, "value", "grp")
    assert result.significance == Significance.NOT_SIGNIFICANT


# --------------------------------------------------------------------------- #
# Group difference: ANOVA (3+ groups)
# --------------------------------------------------------------------------- #
def test_anova_detects_difference_across_three_groups():
    rng = np.random.default_rng(4)
    a = rng.normal(10, 2, size=30)
    b = rng.normal(10, 2, size=30)
    c = rng.normal(18, 2, size=30)  # the odd one out
    df = pd.DataFrame(
        {
            "value": np.concatenate([a, b, c]),
            "grp": (["a"] * 30) + (["b"] * 30) + (["c"] * 30),
        }
    )
    result = group_difference_test(df, "value", "grp")
    assert result.test_kind == TestKind.ANOVA
    assert result.significance == Significance.SIGNIFICANT
    assert result.effect_metric == "eta_squared"


# --------------------------------------------------------------------------- #
# Chi-square (categorical vs categorical)
# --------------------------------------------------------------------------- #
def test_chi_square_detects_association():
    # Build a table where category strongly predicts outcome.
    rows = []
    for _ in range(60):
        rows.append({"grp": "x", "outcome": "yes"})
        rows.append({"grp": "y", "outcome": "no"})
    # add a little noise so it is not perfectly separable
    for _ in range(5):
        rows.append({"grp": "x", "outcome": "no"})
        rows.append({"grp": "y", "outcome": "yes"})
    df = pd.DataFrame(rows)
    result = chi_square_test(df, "grp", "outcome")
    assert result.test_kind == TestKind.CHI_SQUARE
    assert result.significance == Significance.SIGNIFICANT
    assert result.effect_value > 0.3


def test_chi_square_independent_categories():
    rng = np.random.default_rng(5)
    df = pd.DataFrame(
        {
            "grp": rng.choice(["x", "y"], size=200),
            "outcome": rng.choice(["yes", "no"], size=200),
        }
    )
    result = chi_square_test(df, "grp", "outcome")
    assert result.significance == Significance.NOT_SIGNIFICANT


# --------------------------------------------------------------------------- #
# Full engine orchestration
# --------------------------------------------------------------------------- #
def test_engine_runs_and_applies_bonferroni():
    rng = np.random.default_rng(6)
    n = 120
    x = np.linspace(0, 10, n) + 0.3
    df = pd.DataFrame(
        {
            "x": x,
            "y": 2 * x + rng.normal(0, 1, n),          # correlated with x
            "noise": rng.normal(size=n) + 0.5,          # correlated with nothing
            "grp": rng.choice(["a", "b", "c"], size=n),
        }
    )
    report = analyze_significance(df)
    assert report.n_tests >= 1
    # With more than one test, a Bonferroni threshold must be computed.
    if report.n_tests > 1:
        assert report.bonferroni_alpha is not None
        assert report.bonferroni_alpha < report.alpha
    assert len(report.summary) > 0


def test_engine_target_adds_chi_square():
    # survived (binary) vs sex (binary) should produce a chi-square test.
    df = pd.DataFrame(
        {
            "survived": ([1] * 30) + ([0] * 30),
            "sex": (["female"] * 25 + ["male"] * 5) + (["female"] * 5 + ["male"] * 25),
        }
    )
    report = analyze_significance(df, target="survived")
    kinds = {t.test_kind for t in report.tests}
    assert TestKind.CHI_SQUARE in kinds


def test_report_helpers():
    df = pd.DataFrame(
        {
            "a": np.linspace(0, 5, 50) + 0.2,
            "b": np.linspace(0, 5, 50) * 2 + 0.1,
        }
    )
    report = analyze_significance(df)
    # significant() should be a subset of all tests
    assert all(t.significance == Significance.SIGNIFICANT for t in report.significant())
    assert len(report.significant()) <= report.n_tests
