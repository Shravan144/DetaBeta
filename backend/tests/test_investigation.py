"""
Tests for the Investigation Engine (Engine 3).

Strategy: build tiny, hand-crafted DataFrames where we KNOW the right answer,
so each test pins down one detector's behaviour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.investigation import investigate
from engines.investigation.types import FindingType, Strength


# --- correlations -------------------------------------------------------------

def test_detects_strong_positive_correlation():
    # y is almost exactly 2*x -> a very strong positive linear correlation.
    # We add a fractional offset so y stays CONTINUOUS: without it, y would be
    # all-unique whole numbers and Engine 1 would (correctly) tag it an
    # IDENTIFIER, which is excluded from correlation.
    x = [float(v) + 0.5 for v in range(30)]
    y = [2.0 * v + 1.3 for v in x]
    df = pd.DataFrame({"x": x, "y": y})

    report = investigate(df)
    corr = report.of_type(FindingType.CORRELATION)
    assert len(corr) == 1
    f = corr[0]
    assert set(f.columns) == {"x", "y"}
    assert f.direction == "positive"
    assert f.evidence["pearson_r"] > 0.95
    assert f.strength == Strength.VERY_STRONG


def test_detects_negative_correlation():
    x = [float(v) + 0.5 for v in range(30)]
    y = [-3.0 * v for v in x]
    df = pd.DataFrame({"x": x, "y": y})

    corr = investigate(df).of_type(FindingType.CORRELATION)
    assert len(corr) == 1
    assert corr[0].direction == "negative"


def test_ignores_weak_correlation():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "a": rng.normal(size=200),
        "b": rng.normal(size=200),
    })
    corr = investigate(df).of_type(FindingType.CORRELATION)
    assert corr == []  # independent noise -> nothing surfaced


def test_flags_nonlinear_relationship():
    # y = x^2 over positive x is monotonic (strong Spearman) but not perfectly
    # linear -> Spearman should exceed Pearson and set the nonlinear hint.
    x = [float(v) + 0.5 for v in range(30)]
    y = [v ** 2 for v in x]
    df = pd.DataFrame({"x": x, "y": y})
    corr = investigate(df).of_type(FindingType.CORRELATION)
    assert len(corr) == 1
    assert corr[0].evidence["spearman_r"] >= corr[0].evidence["pearson_r"]


# --- group differences --------------------------------------------------------

def test_detects_group_difference():
    # Two groups with clearly different score levels.
    group = ["A"] * 15 + ["B"] * 15
    score = [10.0 + i * 0.1 for i in range(15)] + [90.0 + i * 0.1 for i in range(15)]
    df = pd.DataFrame({"group": group, "score": score})

    findings = investigate(df).of_type(FindingType.GROUP_DIFFERENCE)
    assert len(findings) >= 1
    gd = findings[0]
    assert "group" in gd.columns and "score" in gd.columns
    assert gd.evidence["highest_group"] == "B"
    assert gd.evidence["lowest_group"] == "A"


# --- target relationships -----------------------------------------------------

def test_target_relationship_for_categorical_target():
    # 'feature' cleanly separates the two target classes.
    target = ["yes"] * 15 + ["no"] * 15
    feature = [100.0 + i * 0.1 for i in range(15)] + [1.0 + i * 0.1 for i in range(15)]
    df = pd.DataFrame({"outcome": target, "feature": feature})

    report = investigate(df, target="outcome")
    tr = report.of_type(FindingType.TARGET_RELATIONSHIP)
    assert len(tr) >= 1
    assert "feature" in tr[0].columns
    assert tr[0].needs_significance_test is True


def test_no_target_relationships_without_target():
    df = pd.DataFrame({
        "outcome": ["yes"] * 15 + ["no"] * 15,
        "feature": [float(i) + 0.5 for i in range(30)],
    })
    report = investigate(df)  # no target passed
    assert report.of_type(FindingType.TARGET_RELATIONSHIP) == []


# --- skew ---------------------------------------------------------------------

def test_detects_skewed_distribution():
    # A long right tail: many small values, a few huge ones.
    values = [float(i) + 0.5 for i in range(40)] + [5000.0, 6000.0, 7000.0]
    df = pd.DataFrame({"amount": values})
    skew = investigate(df).of_type(FindingType.DISTRIBUTION_SKEW)
    assert len(skew) == 1
    assert skew[0].direction == "right"
    assert skew[0].needs_significance_test is False  # skew is a fact


# --- dominant category --------------------------------------------------------

def test_detects_dominant_category():
    # 'flag' is 'N' for 95% of rows.
    flag = ["N"] * 95 + ["Y"] * 5
    other = [float(i) + 0.5 for i in range(100)]
    df = pd.DataFrame({"flag": flag, "measure": other})
    dom = investigate(df).of_type(FindingType.DOMINANT_CATEGORY)
    assert len(dom) == 1
    assert dom[0].evidence["top_level"] == "N"
    assert dom[0].evidence["top_pct"] >= 90.0


# --- ranking & report ---------------------------------------------------------

def test_findings_are_sorted_by_score_desc():
    x = [float(v) + 0.5 for v in range(40)]
    df = pd.DataFrame({
        "x": x,
        "y": [2.0 * v for v in x],            # strong correlation
        "amount": x + [],                      # mild
    })
    report = investigate(df)
    scores = [f.score for f in report.findings]
    assert scores == sorted(scores, reverse=True)


def test_empty_of_patterns_reports_gracefully():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "a": rng.normal(size=100),
        "b": rng.normal(size=100),
    })
    report = investigate(df)
    assert report.n_findings == 0
    assert any("No strong patterns" in line for line in report.summary)
