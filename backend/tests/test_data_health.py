"""
Tests for Engine 2 (Data Health).

These tests build small, purpose-made DataFrames so each health check can be
verified in isolation, then a couple of integration tests confirm the whole
report hangs together. We assert on behaviour a human cares about (severity,
category, that a recommendation exists) rather than exact wording.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engines.data_health import assess_health
from engines.data_health.types import IssueCategory, Severity


# --- Missing values ----------------------------------------------------------
def test_detects_missing_values():
    df = pd.DataFrame({"age": [10, 20, np.nan, 40, np.nan, 60, 70, 80]})
    report = assess_health(df)
    missing = report.issues_in_category(IssueCategory.MISSING)
    assert len(missing) == 1
    assert missing[0].column == "age"
    assert missing[0].recommendation  # a recommendation must be present
    assert missing[0].reasoning        # with reasoning


def test_no_missing_means_no_missing_issue():
    df = pd.DataFrame({"age": [10, 20, 30, 40], "score": [1.1, 2.2, 3.3, 4.4]})
    report = assess_health(df)
    assert report.issues_in_category(IssueCategory.MISSING) == []


def test_critical_missing_recommends_drop():
    # 80% missing -> should be CRITICAL and recommend dropping.
    col = [1.0] + [np.nan] * 9
    df = pd.DataFrame({"mostly_empty": col, "keep": range(10)})
    report = assess_health(df)
    issues = report.issues_in_category(IssueCategory.MISSING)
    target = [i for i in issues if i.column == "mostly_empty"][0]
    assert target.severity == Severity.CRITICAL
    assert "drop" in target.recommendation.lower()


# --- Duplicates --------------------------------------------------------------
def test_detects_duplicate_rows():
    df = pd.DataFrame({"a": [1, 2, 2, 3], "b": ["x", "y", "y", "z"]})
    report = assess_health(df)
    dupes = report.issues_in_category(IssueCategory.DUPLICATES)
    assert len(dupes) == 1
    assert dupes[0].evidence["n_duplicate_rows"] == 1


# --- Constant columns --------------------------------------------------------
def test_detects_constant_column():
    df = pd.DataFrame({"const": [7, 7, 7, 7], "varies": [1, 2, 3, 4]})
    report = assess_health(df)
    consts = report.issues_in_category(IssueCategory.CONSTANT)
    assert len(consts) == 1
    assert consts[0].column == "const"


# --- Outliers ----------------------------------------------------------------
def test_detects_outliers():
    # Fractional values so Engine 1 sees a CONTINUOUS measurement (not an
    # all-integer identifier). 0.5..19.5 are tame; 100000.5 is a blatant
    # outlier by the IQR rule.
    values = [float(v) + 0.5 for v in range(20)] + [100000.5]
    df = pd.DataFrame({"income": values})
    report = assess_health(df)
    outliers = report.issues_in_category(IssueCategory.OUTLIERS)
    assert len(outliers) == 1
    assert outliers[0].evidence["n_outliers"] >= 1


def test_no_outliers_in_uniform_data():
    df = pd.DataFrame({"x": [float(v) for v in range(50)]})
    report = assess_health(df)
    assert report.issues_in_category(IssueCategory.OUTLIERS) == []


# --- Class imbalance ---------------------------------------------------------
def test_detects_class_imbalance():
    # 1 positive out of 20 -> 5% minority -> HIGH imbalance.
    df = pd.DataFrame({"target": [1] + [0] * 19})
    report = assess_health(df)
    imbalance = report.issues_in_category(IssueCategory.IMBALANCE)
    assert len(imbalance) == 1
    assert imbalance[0].severity == Severity.HIGH


def test_balanced_binary_not_flagged():
    df = pd.DataFrame({"target": [0, 1] * 10})
    report = assess_health(df)
    assert report.issues_in_category(IssueCategory.IMBALANCE) == []


# --- Inconsistent values -----------------------------------------------------
def test_detects_inconsistent_values():
    # "USA", "usa", " USA " are the same value typed three ways.
    df = pd.DataFrame(
        {"country": ["USA", "usa", " USA ", "India", "India", "India", "UK", "UK"]}
    )
    report = assess_health(df)
    inconsistent = report.issues_in_category(IssueCategory.INCONSISTENCY)
    assert len(inconsistent) == 1
    assert inconsistent[0].column == "country"


# --- Scoring -----------------------------------------------------------------
def test_clean_dataset_scores_high():
    df = pd.DataFrame(
        {
            "age": [21, 34, 45, 29, 51, 38, 42, 33],
            "city": ["A", "B", "A", "B", "A", "B", "A", "B"],
        }
    )
    report = assess_health(df)
    assert report.score >= 90
    assert report.grade == "A"


def test_messy_dataset_scores_lower():
    df = pd.DataFrame(
        {
            "id": range(10),
            "val": [1.0, np.nan, np.nan, np.nan, np.nan, 6.0, 7.0, 8.0, 9.0, 10.0],
            "flag": [1] + [0] * 9,
        }
    )
    report = assess_health(df)
    assert report.score < 90
    assert len(report.issues) >= 1


def test_report_is_sorted_by_severity():
    df = pd.DataFrame(
        {
            "val": [1.0, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 8.0, 9.0, 10.0],
            "flag": [1] + [0] * 9,
        }
    )
    report = assess_health(df)
    order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    ranks = [order[i.severity] for i in report.issues]
    assert ranks == sorted(ranks)


# --- Integration on the shipped messy sample --------------------------------
def test_messy_sample_file_produces_many_issues():
    from pathlib import Path

    path = Path(__file__).parent.parent / "sample_data" / "messy_customers.csv"
    df = pd.read_csv(path)
    report = assess_health(df)
    categories = {i.category for i in report.issues}
    # The file was engineered to contain all of these problems.
    assert IssueCategory.MISSING in categories
    assert IssueCategory.DUPLICATES in categories
    assert IssueCategory.INCONSISTENCY in categories
    assert report.score < 100
