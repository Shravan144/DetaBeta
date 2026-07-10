"""
Engine 6 orchestrator: turn a dataset + a chosen target into a full,
evidence-backed modelling plan.

Pipeline:
    understand_dataset (Engine 1)         # reuse column meanings
        -> detect_problem_type            # classification vs regression
        -> select_features                # what to model on, what to drop
        -> recommend_algorithms           # ranked, with reasoning
        -> plan_validation                # how to evaluate honestly
        -> warnings + summary
"""

from __future__ import annotations

import pandas as pd

from ..dataset_understanding import understand_dataset
from ..dataset_understanding.types import DatasetProfile, SemanticType
from .recommend import (
    detect_problem_type,
    plan_validation,
    recommend_algorithms,
    select_features,
)
from .types import MLRecommendationReport, ProblemType


def recommend_model(
    data: pd.DataFrame | DatasetProfile,
    target: str,
    raw_df: pd.DataFrame | None = None,
) -> MLRecommendationReport:
    """
    Produce a modelling plan for predicting `target`.

    `data` may be a raw DataFrame (we'll profile it) or an already-computed
    DatasetProfile (so callers can reuse Engine 1's work without recomputing).
    """
    if isinstance(data, DatasetProfile):
        profile = data
    else:
        profile = understand_dataset(data)

    n_rows = profile.n_rows

    # --- Validate the target exists ------------------------------------- #
    target_col = profile.column(target)
    if target_col is None:
        return MLRecommendationReport(
            target=target,
            problem_type=ProblemType.UNKNOWN,
            problem_reasoning=[
                f"Column '{target}' was not found in the dataset. "
                f"Available columns: {', '.join(c.name for c in profile.columns)}."
            ],
            summary=f"Cannot build a plan: target column '{target}' does not exist.",
        )

    # --- Step 1: problem type ------------------------------------------- #
    problem_type, problem_reasoning = detect_problem_type(target_col)

    report = MLRecommendationReport(
        target=target,
        problem_type=problem_type,
        problem_reasoning=problem_reasoning,
    )

    if problem_type == ProblemType.UNKNOWN:
        report.summary = (
            f"'{target}' cannot be used as a prediction target. "
            "Pick a binary, categorical, or numeric column instead."
        )
        return report

    # --- Step 2: features ----------------------------------------------- #
    features, excluded = select_features(profile, target)
    report.feature_columns = features
    report.excluded_columns = excluded

    if not features:
        report.warnings.append(
            "No usable feature columns remain after exclusions -- the model would "
            "have nothing to learn from."
        )

    # --- Step 3: algorithms --------------------------------------------- #
    report.algorithms = recommend_algorithms(
        problem_type=problem_type,
        n_rows=n_rows,
        n_features=len(features),
    )

    # --- Step 4: validation --------------------------------------------- #
    report.validation = plan_validation(problem_type, n_rows, target_col)

    # --- Warnings: honest reality checks -------------------------------- #
    report.warnings.extend(_build_warnings(profile, target_col, n_rows, len(features)))

    # --- Summary --------------------------------------------------------- #
    report.summary = _build_summary(report, n_rows)
    return report


def _build_warnings(
    profile: DatasetProfile,
    target_col,
    n_rows: int,
    n_features: int,
) -> list[str]:
    """Collect honest, evidence-based cautions about this modelling setup."""
    warnings: list[str] = []

    # Tiny dataset.
    if n_rows < 50:
        warnings.append(
            f"Only {n_rows} rows: any model will be unreliable and scores will "
            "vary wildly. Treat results as illustrative, not trustworthy."
        )
    elif n_rows < 200:
        warnings.append(
            f"{n_rows} rows is small; prefer simple models and cross-validation, "
            "and be cautious about strong conclusions."
        )

    # Curse of dimensionality: too many features for too few rows.
    if n_features and n_rows and n_features > n_rows / 10:
        warnings.append(
            f"{n_features} features for {n_rows} rows is a high ratio -- models "
            "can overfit. Consider feature selection (see the Feature Lab)."
        )

    # Target missing values.
    if target_col.missing_pct > 0:
        warnings.append(
            f"The target '{target_col.name}' has {target_col.missing_pct:.0f}% "
            "missing values; those rows cannot be used for supervised training."
        )

    # Class imbalance (classification only).
    top_values = target_col.stats.get("top_values") or {}
    if top_values and target_col.n_total:
        top_share = max(top_values.values()) / target_col.n_total
        if top_share >= 0.9:
            warnings.append(
                f"Severe class imbalance: one class is {top_share * 100:.0f}% of "
                "rows. Use F1/ROC-AUC (not accuracy) and consider resampling."
            )

    return warnings


def _build_summary(report: MLRecommendationReport, n_rows: int) -> str:
    """Write the one-paragraph plain-language plan summary."""
    pretty = report.problem_type.value.replace("_", " ")
    baseline = report.baseline()
    baseline_txt = baseline.name if baseline else "a simple baseline"
    n_algos = len(report.algorithms)
    metric = report.validation.primary_metric if report.validation else "an appropriate metric"
    strategy = report.validation.strategy if report.validation else "cross-validation"

    return (
        f"Predicting '{report.target}' is a {pretty} problem on {n_rows} rows "
        f"using {len(report.feature_columns)} feature(s). Start with {baseline_txt} "
        f"as your baseline, then compare {n_algos - 1} more capable model(s). "
        f"Evaluate with {strategy}, optimising {metric.upper()}. "
        f"{len(report.warnings)} caution(s) were raised -- review them before trusting results."
    )
