"""
Dataset Understanding Engine (Engine 1) -- orchestrator.

This is the public entry point of Engine 1. It answers the question:

    "What kind of data is this?"

Give it a pandas DataFrame and it returns a DatasetProfile: a per-column
classification (with reasoning) plus dataset-level observations. It performs
NO cleaning, NO plotting, NO modelling. Its only job is understanding.

Everything downstream (health checks, statistics, feature engineering, ML)
depends on getting this understanding right, which is why it is the first
engine we build.
"""

from __future__ import annotations

import pandas as pd

from .classifier import classify_column
from .types import DatasetProfile, SemanticType


def understand_dataset(df: pd.DataFrame) -> DatasetProfile:
    """
    Analyse a DataFrame and return a fully-populated DatasetProfile.

    Steps:
      1. Classify every column individually (delegated to classify_column).
      2. Compute dataset-level roll-ups (duplicates, memory).
      3. Generate plain-language observations a human can learn from.
    """
    n_rows, n_cols = df.shape

    profile = DatasetProfile(n_rows=n_rows, n_cols=n_cols)

    # --- Step 1: classify each column ---------------------------------------
    for col_name in df.columns:
        profile.columns.append(classify_column(df[col_name]))

    # --- Step 2: dataset-level facts ----------------------------------------
    profile.memory_usage_bytes = int(df.memory_usage(deep=True).sum())
    profile.n_duplicate_rows = int(df.duplicated().sum())

    # --- Step 3: turn facts into teaching observations ----------------------
    profile.observations = _build_observations(profile)

    return profile


def _build_observations(profile: DatasetProfile) -> list[str]:
    """
    Summarise the dataset in a few human sentences.

    These observations are what a UI would surface first -- the "at a glance"
    story of the dataset, in DetaBeta's explain-everything spirit.
    """
    obs: list[str] = []

    obs.append(
        f"This dataset has {profile.n_rows} rows and {profile.n_cols} columns."
    )

    # Group columns by semantic type for a quick composition summary.
    counts: dict[SemanticType, int] = {}
    for col in profile.columns:
        counts[col.semantic_type] = counts.get(col.semantic_type, 0) + 1

    composition = ", ".join(
        f"{n} {t.value.replace('_', ' ')}"
        for t, n in sorted(counts.items(), key=lambda kv: kv[0].value)
    )
    obs.append(f"Column make-up: {composition}.")

    # Flag identifiers -- important because they must be excluded from modelling.
    ids = profile.columns_of_type(SemanticType.IDENTIFIER)
    if ids:
        names = ", ".join(f"'{c.name}'" for c in ids)
        obs.append(
            f"{len(ids)} column(s) look like identifiers ({names}). We will "
            f"exclude these from modelling to avoid leakage."
        )

    # Flag constants -- zero information.
    consts = profile.columns_of_type(SemanticType.CONSTANT)
    if consts:
        names = ", ".join(f"'{c.name}'" for c in consts)
        obs.append(
            f"{len(consts)} column(s) are constant ({names}) and carry no "
            f"information, so they are candidates to drop."
        )

    # Flag likely prediction targets (binary columns are the classic case).
    binaries = profile.columns_of_type(SemanticType.BINARY)
    if binaries:
        names = ", ".join(f"'{c.name}'" for c in binaries)
        obs.append(
            f"{len(binaries)} binary column(s) ({names}) could serve as a "
            f"classification target."
        )

    # Flag missing-data hotspots.
    missing = sorted(
        (c for c in profile.columns if c.missing_pct > 0),
        key=lambda c: c.missing_pct,
        reverse=True,
    )
    if missing:
        worst = missing[0]
        obs.append(
            f"{len(missing)} column(s) have missing values; the worst is "
            f"'{worst.name}' at {worst.missing_pct}% missing. Engine 2 (Health) "
            f"will recommend how to handle these."
        )
    else:
        obs.append("No missing values detected in any column.")

    # Flag duplicate rows.
    if profile.n_duplicate_rows > 0:
        obs.append(
            f"{profile.n_duplicate_rows} duplicate row(s) detected -- these may "
            f"bias results and are worth reviewing."
        )

    return obs
