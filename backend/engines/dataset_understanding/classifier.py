"""
Column classifier for the Dataset Understanding Engine (Engine 1).

Given a single pandas Series (one column), decide its SemanticType and record
the reasoning behind the decision.

The design principle: a small ladder of checks, from most certain to least.
We stop at the first check that confidently applies. Every rung on the ladder
appends a human-readable sentence to `profile.reasoning`, so the final result
reads like an explanation a teacher would give.

Order of the decision ladder (most decisive first):
    1. Constant?      -> only one distinct value  -> CONSTANT
    2. Datetime?      -> pandas datetime dtype     -> DATETIME
    3. Binary?        -> exactly two distinct values -> BINARY
    4. Numeric?       -> number dtype -> continuous vs discrete vs identifier
    5. Text vs Categorical? -> object/string dtype: few labels vs free text
    6. Fallback       -> UNKNOWN
"""

from __future__ import annotations

import pandas as pd
from pandas.api import types as ptypes

from .types import ColumnProfile, SemanticType

# --- Tunable thresholds -------------------------------------------------------
# These are heuristics, not laws. They are gathered here (instead of buried in
# the code) so they are easy to find, explain, and tune later.

# If a numeric column has this few distinct values, treat it as discrete counts
# rather than a continuous measurement.
MAX_DISCRETE_UNIQUE = 20

# If a text/object column's values are almost all unique, it is probably free
# text or an identifier, not a category. 0.9 = 90% of values are distinct.
HIGH_CARDINALITY_RATIO = 0.9

# A numeric column whose values are (nearly) all unique is likely an ID.
ID_UNIQUE_RATIO = 0.98


def classify_column(series: pd.Series) -> ColumnProfile:
    """
    Classify a single column and return a fully-populated ColumnProfile.

    We compute the universal counts once, then walk the decision ladder.
    """
    name = str(series.name)
    profile = ColumnProfile(
        name=name,
        raw_dtype=str(series.dtype),
        semantic_type=SemanticType.UNKNOWN,
    )

    # ---- Universal facts (true for every column) ----------------------------
    n_total = len(series)
    non_null = series.dropna()
    n_missing = n_total - len(non_null)
    n_unique = int(non_null.nunique())

    profile.n_total = n_total
    profile.n_missing = int(n_missing)
    profile.missing_pct = round(100 * n_missing / n_total, 2) if n_total else 0.0
    profile.n_unique = n_unique
    profile.unique_pct = round(100 * n_unique / len(non_null), 2) if len(non_null) else 0.0
    profile.sample_values = [_json_safe(v) for v in non_null.head(5).tolist()]

    profile.add_reason(
        f"Column '{name}' is stored by pandas as '{profile.raw_dtype}', "
        f"has {n_total} rows, {profile.n_missing} missing "
        f"({profile.missing_pct}%), and {n_unique} distinct values."
    )

    # ---- Rung 1: Constant ---------------------------------------------------
    # A column with 0 or 1 distinct values carries no information for analysis.
    if n_unique <= 1:
        profile.semantic_type = SemanticType.CONSTANT
        profile.add_reason(
            "It has one distinct value (or none), so it is CONSTANT and cannot "
            "help distinguish rows. We usually drop constant columns."
        )
        return profile

    # ---- Rung 2: Datetime ---------------------------------------------------
    if ptypes.is_datetime64_any_dtype(series):
        profile.semantic_type = SemanticType.DATETIME
        profile.add_reason(
            "pandas parsed it as a datetime dtype, so it represents points in "
            "time. Time columns unlock trends, seasonality, and recency features."
        )
        profile.stats = _datetime_stats(non_null)
        return profile

    # ---- Rung 3: Binary -----------------------------------------------------
    # Exactly two distinct values is special: it is the simplest classification
    # target and is handled differently from a multi-class category.
    if n_unique == 2:
        profile.semantic_type = SemanticType.BINARY
        values = sorted(non_null.unique().tolist(), key=lambda v: str(v))
        profile.add_reason(
            f"It has exactly two distinct values ({_json_safe(values[0])!r} and "
            f"{_json_safe(values[1])!r}), so it is BINARY -- a natural yes/no or "
            f"0/1 flag, and a common prediction target."
        )
        profile.stats = _category_stats(non_null)
        return profile

    # ---- Rung 4: Numeric ----------------------------------------------------
    if ptypes.is_numeric_dtype(series) and not ptypes.is_bool_dtype(series):
        return _classify_numeric(series, non_null, profile)

    # ---- Rung 5: Object / string -> text vs categorical ---------------------
    if ptypes.is_object_dtype(series) or ptypes.is_string_dtype(series):
        return _classify_text_like(non_null, profile)

    # ---- Rung 6: Boolean dtype (explicit) -----------------------------------
    if ptypes.is_bool_dtype(series):
        profile.semantic_type = SemanticType.BINARY
        profile.add_reason(
            "It is a true/false boolean column, which is BINARY by definition."
        )
        profile.stats = _category_stats(non_null)
        return profile

    # ---- Rung 7: Give up honestly -------------------------------------------
    profile.add_reason(
        "None of the confident rules matched, so we mark it UNKNOWN rather than "
        "guess. A human should inspect this column."
    )
    return profile


# --- Helpers for the numeric branch ------------------------------------------

def _classify_numeric(
    series: pd.Series, non_null: pd.Series, profile: ColumnProfile
) -> ColumnProfile:
    """Decide between IDENTIFIER, NUMERIC_DISCRETE and NUMERIC_CONTINUOUS."""
    n_unique = profile.n_unique
    unique_ratio = n_unique / len(non_null) if len(non_null) else 0

    # Is it secretly an ID? All-integer AND almost every value is unique.
    looks_integer = _all_integer_valued(non_null)
    if looks_integer and unique_ratio >= ID_UNIQUE_RATIO:
        profile.semantic_type = SemanticType.IDENTIFIER
        profile.add_reason(
            f"Although it is numeric, {profile.unique_pct}% of its values are "
            f"unique and all are whole numbers -- that is the fingerprint of an "
            f"IDENTIFIER (like an ID or row key), not a measurement. IDs must be "
            f"excluded from modelling or they cause data leakage."
        )
        profile.stats = _numeric_stats(non_null)
        return profile

    # Few distinct whole numbers -> discrete counts.
    if looks_integer and n_unique <= MAX_DISCRETE_UNIQUE:
        profile.semantic_type = SemanticType.NUMERIC_DISCRETE
        profile.add_reason(
            f"It holds whole numbers with only {n_unique} distinct values "
            f"(<= {MAX_DISCRETE_UNIQUE}), so it behaves like a DISCRETE count "
            f"(e.g. number of items) rather than a smooth measurement."
        )
        profile.stats = _numeric_stats(non_null)
        return profile

    # Otherwise: a continuous measurement.
    profile.semantic_type = SemanticType.NUMERIC_CONTINUOUS
    profile.add_reason(
        f"It is numeric with {n_unique} distinct values spread across a range, "
        f"so it is a CONTINUOUS measurement. Continuous columns support means, "
        f"correlations, scaling, and distribution plots."
    )
    profile.stats = _numeric_stats(non_null)
    return profile


def _classify_text_like(non_null: pd.Series, profile: ColumnProfile) -> ColumnProfile:
    """Decide between CATEGORICAL, TEXT and IDENTIFIER for object columns."""
    n_unique = profile.n_unique
    unique_ratio = n_unique / len(non_null) if len(non_null) else 0

    # Almost every value unique -> either an ID code or free text.
    if unique_ratio >= HIGH_CARDINALITY_RATIO:
        # Short, no spaces -> looks like an ID code; long/spaced -> free text.
        avg_len = float(non_null.astype(str).str.len().mean())
        has_spaces = bool(non_null.astype(str).str.contains(" ").mean() > 0.5)
        if not has_spaces and avg_len <= 20:
            profile.semantic_type = SemanticType.IDENTIFIER
            profile.add_reason(
                f"{profile.unique_pct}% of values are unique and look like short "
                f"codes (avg length {avg_len:.0f}, no spaces), so it is an "
                f"IDENTIFIER. IDs should not be fed to a model as features."
            )
        else:
            profile.semantic_type = SemanticType.TEXT
            profile.add_reason(
                f"{profile.unique_pct}% of values are unique and look like free "
                f"text (avg length {avg_len:.0f}). TEXT needs NLP-style handling, "
                f"not one-hot encoding."
            )
        profile.stats = {"avg_char_length": round(avg_len, 1)}
        return profile

    # A limited label set -> a genuine category.
    profile.semantic_type = SemanticType.CATEGORICAL
    profile.add_reason(
        f"It has a limited set of {n_unique} repeating labels, so it is "
        f"CATEGORICAL. Categories drive group comparisons and one-hot encoding."
    )
    profile.stats = _category_stats(non_null)
    return profile


# --- Stat builders ------------------------------------------------------------

def _numeric_stats(non_null: pd.Series) -> dict:
    desc = non_null.describe()
    return {
        "min": _json_safe(non_null.min()),
        "max": _json_safe(non_null.max()),
        "mean": round(float(non_null.mean()), 4),
        "median": round(float(non_null.median()), 4),
        "std": round(float(non_null.std()), 4) if len(non_null) > 1 else 0.0,
        "q25": round(float(desc.get("25%", non_null.quantile(0.25))), 4),
        "q75": round(float(desc.get("75%", non_null.quantile(0.75))), 4),
        # Skew measures asymmetry: ~0 is symmetric, >0 has a long right tail,
        # <0 a long left tail. Engine 2 uses it to choose mean vs median for
        # imputation (the mean is unreliable when a column is skewed).
        "skew": round(float(non_null.skew()), 4) if len(non_null) > 2 else 0.0,
    }


def _category_stats(non_null: pd.Series) -> dict:
    counts = non_null.value_counts().head(10)
    return {
        "top_values": {
            _json_safe(k): int(v) for k, v in counts.items()
        }
    }


def _datetime_stats(non_null: pd.Series) -> dict:
    return {
        "earliest": str(non_null.min()),
        "latest": str(non_null.max()),
    }


# --- Small utilities ----------------------------------------------------------

def _all_integer_valued(non_null: pd.Series) -> bool:
    """
    True if every value is a whole number, even when stored as float.
    (e.g. a column of ages loaded as 22.0, 30.0 is still "integer valued".)
    """
    if ptypes.is_integer_dtype(non_null):
        return True
    if ptypes.is_float_dtype(non_null):
        return bool((non_null.dropna() % 1 == 0).all())
    return False


def _json_safe(value):
    """
    Convert numpy/pandas scalar types to plain Python so results serialize to
    JSON cleanly later (numpy.int64 is not JSON-serializable by default).
    """
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return value
    return value
