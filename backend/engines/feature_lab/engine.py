"""
Feature Lab Engine (Engine 5) -- orchestrator.

Public entry point: recommend_features(df, profile=None, target=None)

It runs every recommendation detector, ranks the results (ESSENTIAL first),
and writes a plain-language summary. Like the other engines it NEVER mutates
the DataFrame -- it only returns advice the user can choose to apply.

Pipeline position:
    Engine 1 (understand) -> Engine 2 (health) -> Engine 3 (investigate)
    -> Engine 4 (prove)   -> Engine 5 (IMPROVE, here) -> Engine 6/7 (model)
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.dataset_understanding.types import DatasetProfile
from .types import (
    FeatureLabReport,
    FeatureRecommendation,
    PRIORITY_WEIGHT,
    Priority,
)
from .suggestions import (
    suggest_skew_fixes,
    suggest_scaling,
    suggest_outlier_clipping,
    suggest_categorical_encoding,
    suggest_group_rare_categories,
    suggest_datetime_parts,
    suggest_drops,
)


def recommend_features(
    df: pd.DataFrame,
    profile: DatasetProfile | None = None,
    target: str | None = None,
) -> FeatureLabReport:
    """
    Produce a ranked list of feature-engineering recommendations.

    Args:
        df:      the raw dataset.
        profile: an existing Engine 1 profile; if None we compute one so this
                 engine can be used standalone.
        target:  optional name of the column you intend to predict. If given,
                 we avoid recommending transforms *on the target itself* (you
                 engineer features, not the label).

    Returns:
        A FeatureLabReport with recommendations sorted ESSENTIAL -> OPTIONAL.
    """
    if profile is None:
        profile = understand_dataset(df)

    # Gather recommendations from every detector.
    recs: list[FeatureRecommendation] = []
    recs += suggest_drops(profile)
    recs += suggest_categorical_encoding(df, profile)
    recs += suggest_skew_fixes(profile)
    recs += suggest_scaling(profile)
    recs += suggest_outlier_clipping(df, profile)
    recs += suggest_group_rare_categories(df, profile)
    recs += suggest_datetime_parts(profile)

    # If a target was named, don't recommend engineering the label itself.
    if target is not None:
        recs = [r for r in recs if not (len(r.columns) == 1 and r.columns[0] == target)]

    # Rank: ESSENTIAL first, then RECOMMENDED, then OPTIONAL. Stable within tier.
    recs.sort(key=lambda r: PRIORITY_WEIGHT[r.priority], reverse=True)

    report = FeatureLabReport(
        n_rows=len(df),
        n_cols=df.shape[1],
        target=target,
        recommendations=recs,
    )
    report.summary = _build_summary(report)
    return report


def _build_summary(report: FeatureLabReport) -> list[str]:
    """Turn the recommendation list into a few plain-language headlines."""
    lines: list[str] = []
    n = len(report.recommendations)
    if n == 0:
        lines.append(
            "No feature transformations are strictly needed -- the columns are "
            "already in reasonable shape for modelling."
        )
        return lines

    n_essential = len(report.by_priority(Priority.ESSENTIAL))
    n_recommended = len(report.by_priority(Priority.RECOMMENDED))
    n_optional = len(report.by_priority(Priority.OPTIONAL))

    lines.append(
        f"Found {n} feature-engineering opportunit"
        f"{'y' if n == 1 else 'ies'}: "
        f"{n_essential} essential, {n_recommended} recommended, "
        f"{n_optional} optional."
    )

    if n_essential:
        lines.append(
            f"Start with the {n_essential} ESSENTIAL step(s) -- without them a "
            f"model will either error or waste effort on useless columns "
            f"(encodings, dropping identifiers/constants)."
        )
    if report.target:
        lines.append(
            f"Target column '{report.target}' is excluded from feature "
            f"transforms -- you engineer the inputs, not the label."
        )
    lines.append(
        "Every recommendation is advice, not an action: DetaBeta never edits "
        "your data. Copy a snippet to apply it yourself when you agree."
    )
    return lines
