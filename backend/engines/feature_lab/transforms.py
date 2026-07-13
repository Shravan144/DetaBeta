"""
Feature Lab -- the *applier* (Engine 5's optional "do it for me" half).

The rest of Engine 5 only *recommends*; it never touches your data. This module
is what runs when the user explicitly clicks "Apply" on a recommendation. It
takes one recommendation (a TransformType + the column(s) + the evidence numbers
that triggered it) and returns a NEW DataFrame with that single transform
applied.

Design rules that keep this honest and safe:
  - PURE: we operate on a copy and return a new frame; the input is untouched.
  - FAITHFUL: each branch mirrors exactly the code snippet the recommendation
    showed the user, so "Apply" does what the teaching snippet said it would.
  - NON-DESTRUCTIVE WHERE IT MATTERS: transforms that *derive* signal (log, sqrt,
    bin, datetime parts, frequency) ADD a new column and keep the original, so
    no information is lost. Transforms that *correct* a column in place (scale,
    clip, group-rare, binary map) replace it, and structural cleanups (drop,
    one-hot) change the column set as the snippet promised.

Every apply returns a short list of human-readable change notes so the UI/API
can tell the user precisely what happened.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .types import TransformType


class TransformError(ValueError):
    """Raised when a transform cannot be applied (bad column, wrong dtype, ...)."""


def apply_transform(
    df: pd.DataFrame,
    transform: str,
    columns: list[str],
    evidence: dict | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Apply ONE feature transform and return (new_df, change_notes).

    Args:
        transform: a TransformType value (e.g. "log_transform").
        columns:   the column(s) the recommendation targeted.
        evidence:  the recommendation's evidence dict (e.g. clip bounds); used
                   only by transforms that need a parameter.

    Raises TransformError if the transform is unknown or the columns are
    missing / unusable.
    """
    evidence = evidence or {}
    out = df.copy()

    missing = [c for c in columns if c not in out.columns]
    if missing:
        raise TransformError(f"Column(s) not found in dataset: {missing}")

    try:
        kind = TransformType(transform)
    except ValueError as exc:
        raise TransformError(f"Unknown transform type: {transform!r}") from exc

    handler = _HANDLERS.get(kind)
    if handler is None:  # pragma: no cover - every TransformType is mapped
        raise TransformError(f"No applier implemented for {transform!r}.")

    notes = handler(out, columns, evidence)
    return out, notes


# --------------------------------------------------------------------------- #
# Individual transforms. Each mutates `df` in place and returns change notes.
# --------------------------------------------------------------------------- #
def _numeric(df: pd.DataFrame, col: str) -> pd.Series:
    """Coerce a column to numeric, raising a clear error if it isn't numeric."""
    s = pd.to_numeric(df[col], errors="coerce")
    if s.notna().sum() == 0:
        raise TransformError(f"Column '{col}' has no numeric values to transform.")
    return s


def _log_transform(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        s = _numeric(df, col)
        col_min = float(np.nanmin(s.values))
        # Plain log needs strictly positive values; use log1p (log(1+x)) when
        # the column contains zeros, since log(0) is undefined.
        use_log1p = col_min <= 0
        new_col = f"{col}_log"
        df[new_col] = np.log1p(s) if use_log1p else np.log(s)
        fn = "log1p" if use_log1p else "log"
        notes.append(f"Added '{new_col}' = np.{fn}('{col}').")
    return notes


def _sqrt_transform(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        s = _numeric(df, col).clip(lower=0)  # sqrt undefined for negatives
        new_col = f"{col}_sqrt"
        df[new_col] = np.sqrt(s)
        notes.append(f"Added '{new_col}' = np.sqrt('{col}').")
    return notes


def _standard_scale(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        s = _numeric(df, col)
        mean, std = s.mean(), s.std(ddof=0)
        if not std or np.isnan(std):
            notes.append(f"Skipped '{col}' (zero variance, cannot scale).")
            continue
        df[col] = (s - mean) / std
        notes.append(f"Standardised '{col}' in place to mean 0, std 1 (z-score).")
    return notes


def _minmax_scale(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        s = _numeric(df, col)
        lo, hi = s.min(), s.max()
        if hi == lo:
            notes.append(f"Skipped '{col}' (constant, cannot min-max scale).")
            continue
        df[col] = (s - lo) / (hi - lo)
        notes.append(f"Rescaled '{col}' in place to the 0..1 range.")
    return notes


def _clip_outliers(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        s = _numeric(df, col)
        # Prefer the IQR fence the recommendation computed; fall back to 1/99%.
        lo = evidence.get("lower_bound")
        hi = evidence.get("upper_bound")
        if lo is None or hi is None:
            lo, hi = s.quantile(0.01), s.quantile(0.99)
        n_clipped = int(((s < lo) | (s > hi)).sum())
        df[col] = s.clip(lower=lo, upper=hi)
        notes.append(
            f"Clipped {n_clipped} extreme value(s) in '{col}' to "
            f"[{float(lo):.2f}, {float(hi):.2f}]."
        )
    return notes


def _bin_numeric(df, columns, evidence) -> list[str]:
    notes = []
    n_bins = int(evidence.get("n_bins", 4))
    for col in columns:
        s = _numeric(df, col)
        new_col = f"{col}_binned"
        # Quantile bins so each bucket holds a similar count; drop dup edges.
        df[new_col] = pd.qcut(s, q=n_bins, labels=False, duplicates="drop")
        notes.append(f"Added '{new_col}' ({n_bins} quantile buckets of '{col}').")
    return notes


def _one_hot_encode(df_ref, columns, evidence) -> list[str]:
    # get_dummies returns a new frame, so we mutate the caller's frame contents
    # by reassigning columns. We do it by clearing and refilling in place.
    encoded = pd.get_dummies(df_ref, columns=list(columns), prefix=columns)
    # Replace the contents of df_ref with `encoded` in place.
    df_ref.drop(columns=df_ref.columns, inplace=True)
    for c in encoded.columns:
        df_ref[c] = encoded[c].values
    added = [c for c in encoded.columns]
    return [
        f"One-hot encoded {list(columns)} into 0/1 columns "
        f"(dataset now has {len(added)} columns)."
    ]


def _ordinal_encode(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        # Stable, explainable mapping: sort the distinct labels and number them.
        cats = pd.Index(df[col].dropna().unique()).sort_values()
        mapping = {label: i for i, label in enumerate(cats)}
        df[col] = df[col].map(mapping)
        if len(mapping) == 2:
            notes.append(f"Mapped binary '{col}' to 0/1: {mapping}.")
        else:
            notes.append(f"Ordinal-encoded '{col}' into ranks 0..{len(mapping) - 1}.")
    return notes


def _frequency_encode(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        freq = df[col].value_counts(normalize=True)
        new_col = f"{col}_freq"
        df[new_col] = df[col].map(freq)
        notes.append(f"Added '{new_col}' (how common each '{col}' label is).")
    return notes


def _group_rare(df, columns, evidence) -> list[str]:
    notes = []
    threshold = float(evidence.get("threshold_pct", 2.0)) / 100.0
    for col in columns:
        freq = df[col].value_counts(normalize=True)
        rare = freq[freq < threshold].index
        if len(rare) == 0:
            notes.append(f"No rare labels to group in '{col}'.")
            continue
        df[col] = df[col].where(~df[col].isin(rare), other="Other")
        notes.append(f"Folded {len(rare)} rare label(s) in '{col}' into 'Other'.")
    return notes


def _extract_datetime_parts(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        dt = pd.to_datetime(df[col], errors="coerce")
        if dt.notna().sum() == 0:
            raise TransformError(f"Column '{col}' could not be parsed as datetime.")
        df[f"{col}_year"] = dt.dt.year
        df[f"{col}_month"] = dt.dt.month
        df[f"{col}_dayofweek"] = dt.dt.dayofweek
        df[f"{col}_is_weekend"] = (dt.dt.dayofweek >= 5).astype(int)
        notes.append(
            f"Extracted year, month, dayofweek, is_weekend from '{col}'."
        )
    return notes


def _drop_column(df, columns, evidence) -> list[str]:
    df.drop(columns=list(columns), inplace=True)
    return [f"Dropped column(s) {list(columns)}."]


def _text_feature(df, columns, evidence) -> list[str]:
    notes = []
    for col in columns:
        # A simple, honest starter feature: length of the text. Full TF-IDF is
        # left to the user (the snippet shows it) since it explodes the schema.
        new_col = f"{col}_length"
        df[new_col] = df[col].fillna("").astype(str).str.len()
        notes.append(
            f"Added '{new_col}' (character length of '{col}') as a starter "
            f"text feature. See the snippet for full TF-IDF."
        )
    return notes


_HANDLERS = {
    TransformType.LOG_TRANSFORM: _log_transform,
    TransformType.SQRT_TRANSFORM: _sqrt_transform,
    TransformType.STANDARD_SCALE: _standard_scale,
    TransformType.MINMAX_SCALE: _minmax_scale,
    TransformType.CLIP_OUTLIERS: _clip_outliers,
    TransformType.BIN_NUMERIC: _bin_numeric,
    TransformType.ONE_HOT_ENCODE: _one_hot_encode,
    TransformType.ORDINAL_ENCODE: _ordinal_encode,
    TransformType.FREQUENCY_ENCODE: _frequency_encode,
    TransformType.GROUP_RARE_CATEGORIES: _group_rare,
    TransformType.EXTRACT_DATETIME_PARTS: _extract_datetime_parts,
    TransformType.DROP_COLUMN: _drop_column,
    TransformType.TEXT_FEATURE: _text_feature,
}
