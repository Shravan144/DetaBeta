"""
Tests for Engine 5 (Feature Lab).

Each test builds a tiny DataFrame that should trigger exactly one kind of
recommendation, then asserts the engine produces it with the right priority.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.feature_lab import recommend_features, Priority, TransformType


def _transforms(report):
    return {r.transform for r in report.recommendations}


def test_recommends_log_for_strong_right_skew():
    # A power-law-ish column: mostly small, a few enormous -> skew >= 2.0, which
    # is the threshold at which the engine prefers log over the gentler sqrt.
    rng = np.random.default_rng(0)
    values = rng.exponential(scale=100.0, size=400) ** 1.6 + 1.0  # strictly positive
    df = pd.DataFrame({"amount": values})
    report = recommend_features(df)
    # Either a log (strong skew) transform is acceptable evidence of a tail fix,
    # but we specifically engineered skew >= 2.0 so log should win.
    logs = [r for r in report.recommendations
            if r.transform == TransformType.LOG_TRANSFORM]
    assert logs, "expected a log transform for a strongly right-skewed column"
    assert logs[0].columns == ["amount"]
    assert "log" in (logs[0].code_snippet or "")


def test_recommends_one_hot_for_small_category():
    df = pd.DataFrame({
        "color": (["red", "green", "blue"] * 40),
        "val": list(range(120)),
    })
    report = recommend_features(df)
    oh = [r for r in report.recommendations
          if r.transform == TransformType.ONE_HOT_ENCODE]
    assert oh, "expected one-hot encoding for a low-cardinality category"
    assert oh[0].priority == Priority.ESSENTIAL
    assert "get_dummies" in (oh[0].code_snippet or "")


def test_recommends_frequency_encoding_for_high_cardinality():
    # 40 distinct labels -> above the one-hot threshold.
    labels = [f"city_{i}" for i in range(40)]
    df = pd.DataFrame({"city": [labels[i % 40] for i in range(400)]})
    report = recommend_features(df)
    freq = [r for r in report.recommendations
            if r.transform == TransformType.FREQUENCY_ENCODE]
    assert freq, "expected frequency encoding for a high-cardinality category"


def test_recommends_scaling_for_mixed_scales():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "age": rng.uniform(18, 90, size=200),          # small spread
        "income": rng.uniform(10_000, 500_000, size=200),  # huge spread
    })
    report = recommend_features(df)
    scale = [r for r in report.recommendations
             if r.transform == TransformType.STANDARD_SCALE]
    assert scale, "expected scaling when columns live on very different scales"
    assert set(scale[0].columns) >= {"age", "income"}


def test_recommends_dropping_identifier():
    df = pd.DataFrame({
        "user_id": list(range(1, 201)),           # unique -> identifier
        "score": np.random.default_rng(2).uniform(0, 1, size=200),
    })
    report = recommend_features(df)
    drops = [r for r in report.recommendations
             if r.transform == TransformType.DROP_COLUMN
             and r.columns == ["user_id"]]
    assert drops, "expected identifier column to be recommended for dropping"
    assert drops[0].priority == Priority.ESSENTIAL


def test_recommends_dropping_constant_column():
    df = pd.DataFrame({
        "country": ["IN"] * 100,                  # constant
        "x": list(range(100)),
    })
    report = recommend_features(df)
    drops = [r for r in report.recommendations
             if r.transform == TransformType.DROP_COLUMN
             and r.columns == ["country"]]
    assert drops, "expected constant column to be recommended for dropping"


def test_recommends_datetime_extraction():
    # Keep real datetime dtype (no .astype(str)): Engine 1 only tags a column
    # DATETIME when pandas has actually parsed it as a datetime, which is how a
    # real pipeline would load a parsed date column.
    dates = pd.date_range("2020-01-01", periods=200, freq="D")
    df = pd.DataFrame({"signup_date": dates})
    report = recommend_features(df)
    dt = [r for r in report.recommendations
          if r.transform == TransformType.EXTRACT_DATETIME_PARTS]
    assert dt, "expected datetime part extraction for a date column"
    assert "dt.dayofweek" in (dt[0].code_snippet or "")


def test_target_is_excluded_from_recommendations():
    df = pd.DataFrame({
        "label": (["yes", "no"] * 100),
        "x": list(range(200)),
    })
    # Without a target, 'label' (binary) could get an encoding recommendation.
    report = recommend_features(df, target="label")
    for rec in report.recommendations:
        assert rec.columns != ["label"], (
            "the target column should never receive a feature transform"
        )


def test_recommendations_are_ranked_essential_first():
    df = pd.DataFrame({
        "user_id": list(range(1, 201)),                 # ESSENTIAL drop
        "color": (["r", "g", "b", "y"] * 50),           # ESSENTIAL one-hot
        "income": np.random.default_rng(3).exponential(100, size=200) + 1,
    })
    report = recommend_features(df)
    weights = [
        {Priority.ESSENTIAL: 3, Priority.RECOMMENDED: 2, Priority.OPTIONAL: 1}[r.priority]
        for r in report.recommendations
    ]
    assert weights == sorted(weights, reverse=True), (
        "recommendations must be sorted with ESSENTIAL first"
    )


def test_engine_never_mutates_input():
    df = pd.DataFrame({
        "color": (["red", "blue"] * 50),
        "amount": np.random.default_rng(4).exponential(100, size=100) + 1,
    })
    before = df.copy(deep=True)
    recommend_features(df)
    pd.testing.assert_frame_equal(df, before)
