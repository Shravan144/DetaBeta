"""
Tests for Engine 1 (Dataset Understanding).

These tests double as documentation: each one states the data-science
expectation in its name and asserts the engine classifies columns correctly.
Run them from the backend/ folder with:

    source ../.venv/bin/activate
    pytest -v
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from engines.dataset_understanding import SemanticType, understand_dataset
from engines.dataset_understanding.classifier import classify_column


# --- Single-column classification tests --------------------------------------

def test_continuous_numeric_is_detected():
    s = pd.Series([1.2, 3.4, 5.6, 7.8, 2.1, 9.9, 4.4], name="price")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.NUMERIC_CONTINUOUS
    assert "mean" in profile.stats


def test_discrete_numeric_is_detected():
    s = pd.Series([0, 1, 2, 1, 0, 3, 2, 1, 0, 1], name="siblings")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.NUMERIC_DISCRETE


def test_binary_column_is_detected():
    s = pd.Series([0, 1, 1, 0, 1, 0, 0, 1], name="survived")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.BINARY


def test_categorical_column_is_detected():
    s = pd.Series(["red", "green", "blue", "red", "blue", "green"], name="color")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.CATEGORICAL
    assert "top_values" in profile.stats


def test_integer_identifier_is_detected():
    # Every value unique + whole numbers -> identifier, not a measurement.
    s = pd.Series(range(1000, 1100), name="user_id")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.IDENTIFIER


def test_constant_column_is_detected():
    s = pd.Series(["x"] * 50, name="flag")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.CONSTANT


def test_free_text_is_detected():
    s = pd.Series(
        [f"this is unique review number {i} about the product" for i in range(50)],
        name="review",
    )
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.TEXT


def test_datetime_is_detected():
    s = pd.Series(pd.date_range("2020-01-01", periods=30, freq="D"), name="date")
    profile = classify_column(s)
    assert profile.semantic_type == SemanticType.DATETIME


def test_missing_values_are_counted():
    s = pd.Series([1.0, 2.0, np.nan, 4.0, np.nan], name="x")
    profile = classify_column(s)
    assert profile.n_missing == 2
    assert profile.missing_pct == 40.0


def test_every_decision_has_reasoning():
    # The core philosophy: no classification without an explanation.
    s = pd.Series([1.2, 3.4, 5.6, 7.8], name="v")
    profile = classify_column(s)
    assert len(profile.reasoning) >= 1


# --- Whole-dataset tests using the sample CSV --------------------------------

@pytest.fixture
def sample_profile():
    csv_path = Path(__file__).resolve().parent.parent / "sample_data" / "passengers.csv"
    df = pd.read_csv(csv_path)
    return understand_dataset(df)


def test_sample_shape(sample_profile):
    assert sample_profile.n_rows == 20
    assert sample_profile.n_cols == 11


def test_sample_passenger_id_is_identifier(sample_profile):
    assert sample_profile.column("passenger_id").semantic_type == SemanticType.IDENTIFIER


def test_sample_survived_is_binary(sample_profile):
    assert sample_profile.column("survived").semantic_type == SemanticType.BINARY


def test_sample_fare_is_continuous(sample_profile):
    assert sample_profile.column("fare").semantic_type == SemanticType.NUMERIC_CONTINUOUS


def test_sample_sex_is_binary(sample_profile):
    # Only 'male'/'female' appear -> exactly two values -> binary.
    assert sample_profile.column("sex").semantic_type == SemanticType.BINARY


def test_sample_country_is_categorical(sample_profile):
    assert sample_profile.column("country").semantic_type == SemanticType.CATEGORICAL


def test_sample_has_observations(sample_profile):
    assert len(sample_profile.observations) > 0
