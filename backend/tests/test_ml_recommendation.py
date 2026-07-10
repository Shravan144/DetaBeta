"""
Tests for Engine 6 (ML Recommendation).

We check the four reasoning steps: problem-type detection, feature selection,
algorithm ranking, and validation planning -- plus honest warnings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.ml_recommendation import ProblemType, recommend_model


def _make_classification_df(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "user_id": range(1, n + 1),          # identifier -> excluded
            "age": rng.integers(18, 80, n) + 0.5,  # continuous feature
            "score": rng.normal(50, 10, n),        # continuous feature
            "plan": rng.choice(["free", "pro", "team"], n),  # categorical feature
            "churned": rng.choice([0, 1], n),      # binary target
        }
    )


def test_detects_binary_classification():
    df = _make_classification_df()
    report = recommend_model(df, target="churned")
    assert report.problem_type == ProblemType.BINARY_CLASSIFICATION


def test_detects_regression():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "sqft": rng.normal(1500, 400, 300),
            "rooms": rng.integers(1, 6, 300),
            "price": rng.normal(300000, 80000, 300),  # continuous target
        }
    )
    report = recommend_model(df, target="price")
    assert report.problem_type == ProblemType.REGRESSION


def test_detects_multiclass_from_categorical_target():
    rng = np.random.default_rng(2)
    df = pd.DataFrame(
        {
            "petal_len": rng.normal(3, 1, 300),
            "petal_wid": rng.normal(1, 0.5, 300),
            "species": rng.choice(["setosa", "versicolor", "virginica"], 300),
        }
    )
    report = recommend_model(df, target="species")
    assert report.problem_type == ProblemType.MULTICLASS_CLASSIFICATION


def test_identifier_is_excluded_from_features():
    df = _make_classification_df()
    report = recommend_model(df, target="churned")
    assert "user_id" not in report.feature_columns
    assert "user_id" in report.excluded_columns
    assert "leakage" in report.excluded_columns["user_id"].lower()


def test_target_never_in_features():
    df = _make_classification_df()
    report = recommend_model(df, target="churned")
    assert "churned" not in report.feature_columns


def test_first_algorithm_is_a_baseline():
    df = _make_classification_df()
    report = recommend_model(df, target="churned")
    assert report.algorithms, "expected at least one algorithm"
    assert report.algorithms[0].rank == 1
    assert report.baseline() is not None
    assert report.baseline().name == "Logistic Regression"


def test_regression_baseline_is_linear_regression():
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        {
            "x": rng.normal(0, 1, 300),
            "y": rng.normal(10, 3, 300),
        }
    )
    report = recommend_model(df, target="y")
    assert report.baseline().name == "Linear Regression"


def test_large_dataset_suggests_boosting():
    df = _make_classification_df(n=800)
    report = recommend_model(df, target="churned")
    names = [a.name for a in report.algorithms]
    assert any("Gradient Boosting" in n for n in names)


def test_small_dataset_warns_and_skips_boosting():
    df = _make_classification_df(n=40)
    report = recommend_model(df, target="churned")
    names = [a.name for a in report.algorithms]
    assert not any("Gradient Boosting" in n for n in names)
    assert any("rows" in w.lower() for w in report.warnings)


def test_classification_validation_is_stratified():
    df = _make_classification_df()
    report = recommend_model(df, target="churned")
    assert report.validation is not None
    assert report.validation.stratify is True


def test_imbalanced_target_prefers_f1():
    rng = np.random.default_rng(4)
    # 95% zeros, 5% ones -> heavy imbalance.
    target = np.array([0] * 285 + [1] * 15)
    rng.shuffle(target)
    df = pd.DataFrame(
        {
            "feat": rng.normal(0, 1, 300),
            "label": target,
        }
    )
    report = recommend_model(df, target="label")
    assert report.validation.primary_metric == "f1"
    assert any("imbalance" in w.lower() for w in report.warnings)


def test_missing_target_returns_unknown():
    df = _make_classification_df()
    report = recommend_model(df, target="does_not_exist")
    assert report.problem_type == ProblemType.UNKNOWN
    assert "not" in report.summary.lower()
