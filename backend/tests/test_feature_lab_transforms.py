"""
Unit tests for the Feature Lab *applier* (engines/feature_lab/transforms.py).

These verify that clicking "Apply" on a recommendation actually produces the
transform the recommendation promised -- and, crucially, that it NEVER mutates
the caller's DataFrame (DetaBeta's "never overwrite your raw evidence" rule).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engines.feature_lab import TransformError, apply_transform


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fare": [1.0, 2.0, 3.0, 100.0, 5.0, 6.0],
            "age": [10, 20, 30, 40, 50, 60],
            "sex": ["male", "female", "female", "male", "female", "male"],
            "city": ["A", "A", "B", "C", "D", "E"],
            "passenger_id": [1, 2, 3, 4, 5, 6],
            "signup": ["2021-01-01", "2021-06-15", "2021-12-31", "2022-03-01", "2022-07-04", "2022-11-20"],
        }
    )


def test_apply_never_mutates_input():
    df = _sample()
    before = df.copy()
    apply_transform(df, "drop_column", ["passenger_id"])
    pd.testing.assert_frame_equal(df, before)


def test_unknown_transform_raises():
    with pytest.raises(TransformError):
        apply_transform(_sample(), "teleport_column", ["fare"])


def test_missing_column_raises():
    with pytest.raises(TransformError):
        apply_transform(_sample(), "drop_column", ["nope"])


def test_drop_column():
    out, notes = apply_transform(_sample(), "drop_column", ["passenger_id"])
    assert "passenger_id" not in out.columns
    assert any("Dropped" in n for n in notes)


def test_log_transform_adds_column():
    out, _ = apply_transform(_sample(), "log_transform", ["fare"])
    assert "fare_log" in out.columns
    # Original preserved, new column is log1p/log of it.
    assert "fare" in out.columns
    assert np.isclose(out["fare_log"].iloc[3], np.log(100.0))


def test_log_transform_uses_log1p_with_zeros():
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
    out, _ = apply_transform(df, "log_transform", ["x"])
    assert np.isclose(out["x_log"].iloc[0], np.log1p(0.0))  # == 0, not -inf


def test_sqrt_transform_adds_column():
    out, _ = apply_transform(_sample(), "sqrt_transform", ["fare"])
    assert "fare_sqrt" in out.columns
    assert np.isclose(out["fare_sqrt"].iloc[2], np.sqrt(3.0))


def test_standard_scale_in_place():
    out, _ = apply_transform(_sample(), "standard_scale", ["age"])
    assert np.isclose(out["age"].mean(), 0.0, atol=1e-9)
    assert np.isclose(out["age"].std(ddof=0), 1.0, atol=1e-9)


def test_minmax_scale_in_place():
    out, _ = apply_transform(_sample(), "minmax_scale", ["age"])
    assert out["age"].min() == 0.0
    assert out["age"].max() == 1.0


def test_clip_outliers_uses_evidence_bounds():
    out, _ = apply_transform(
        _sample(), "clip_outliers", ["fare"], {"lower_bound": 1.0, "upper_bound": 10.0}
    )
    assert out["fare"].max() == 10.0  # 100 got clipped to 10
    assert out["fare"].min() >= 1.0


def test_one_hot_encode_expands_and_drops_original():
    out, _ = apply_transform(_sample(), "one_hot_encode", ["sex"])
    assert "sex" not in out.columns
    assert "sex_male" in out.columns and "sex_female" in out.columns


def test_ordinal_encode_binary_to_0_1():
    out, _ = apply_transform(_sample(), "ordinal_encode", ["sex"])
    assert set(out["sex"].unique()) <= {0, 1}


def test_frequency_encode_adds_column():
    out, _ = apply_transform(_sample(), "frequency_encode", ["city"])
    assert "city_freq" in out.columns
    # "A" appears twice out of six rows -> frequency 1/3.
    a_rows = out.loc[_sample()["city"] == "A", "city_freq"]
    assert np.allclose(a_rows, 2 / 6)


def test_group_rare_folds_into_other():
    # 'city' has A(2), B,C,D,E each once. With a 20% threshold, the singletons
    # (1/6 ~= 16.7%) are rare and should become "Other".
    out, _ = apply_transform(
        _sample(), "group_rare", ["city"], {"threshold_pct": 20.0}
    )
    assert "Other" in set(out["city"].unique())


def test_extract_datetime_parts():
    out, _ = apply_transform(_sample(), "extract_datetime_parts", ["signup"])
    for suffix in ("year", "month", "dayofweek", "is_weekend"):
        assert f"signup_{suffix}" in out.columns


def test_text_feature_adds_length():
    df = pd.DataFrame({"note": ["hi", "hello", ""]})
    out, _ = apply_transform(df, "text_feature", ["note"])
    assert list(out["note_length"]) == [2, 5, 0]
