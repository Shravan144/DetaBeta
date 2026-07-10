"""
Engine 7 orchestrator: Experiment Studio.

Answers: "Which model performs best?"

Flow:
  1. Ask Engine 6 for the modelling plan (problem type, features, algorithms,
     validation strategy).  [we accept a pre-built plan too, to avoid recompute]
  2. Drop rows with a missing target (you cannot learn from a blank answer).
  3. Build ONE cross-validation splitter shared by every model (fair fight).
  4. Train + score each recommended algorithm inside a leak-free pipeline.
  5. Rank by the primary metric, pick a winner, and compare it to the baseline.
  6. Explain everything in plain language.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.ml_recommendation import recommend_model
from engines.ml_recommendation.types import MLRecommendationReport, ProblemType

from .preprocessing import build_preprocessor, split_feature_types
from .trainer import (
    build_estimator,
    evaluate_model,
    make_cv,
    needs_scaling,
    scorers_for,
)
from .types import ExperimentReport, MetricScore, ModelResult


def run_experiment(
    df: pd.DataFrame,
    target: str,
    plan: MLRecommendationReport | None = None,
    max_models: int = 4,
) -> ExperimentReport:
    """
    Train and compare the models Engine 6 recommended for `target`.

    `plan` is optional: pass an existing Engine 6 report to avoid recomputing
    it; otherwise we call Engine 6 ourselves. `max_models` caps how many
    algorithms we actually train (they are tried in Engine 6's rank order).
    """
    if plan is None:
        plan = recommend_model(df, target=target)

    report = ExperimentReport(
        target=target,
        problem_type=plan.problem_type.value,
        primary_metric=plan.validation.primary_metric if plan.validation else "",
    )

    # --- Guard: did Engine 6 find a usable problem? --- #
    if plan.problem_type == ProblemType.UNKNOWN or not plan.feature_columns:
        report.warnings.append(
            "Engine 6 could not produce a usable modelling plan (unknown problem "
            "type or no usable features), so no models were trained."
        )
        report.summary = "No experiment was run because the modelling plan was not usable."
        return report

    # --- Drop rows with a missing target --- #
    work = df.copy()
    before = len(work)
    work = work[work[target].notna()]
    dropped = before - len(work)
    if dropped:
        report.warnings.append(
            f"Dropped {dropped} row(s) with a missing '{target}' value -- a model "
            "cannot learn from rows that have no answer."
        )

    y = work[target]
    profile = understand_dataset(work)
    numeric, categorical = split_feature_types(profile, plan.feature_columns)
    feature_cols = numeric + categorical
    X = work[feature_cols]

    report.n_rows_used = len(work)
    report.n_features_used = len(feature_cols)

    if not feature_cols:
        report.warnings.append("No usable numeric or categorical features remained.")
        report.summary = "No experiment was run because no usable features remained."
        return report

    # --- Shared cross-validation splitter (identical folds for every model) --- #
    stratify = bool(plan.validation and plan.validation.stratify)
    n_folds = plan.validation.n_folds if plan.validation else 5
    cv, used_folds = make_cv(plan.problem_type.value, n_folds, stratify, y)
    if used_folds < n_folds:
        report.warnings.append(
            f"Reduced to {used_folds}-fold cross-validation because the smallest "
            "class (or the dataset) did not have enough rows for more folds."
        )

    metric_names = [plan.validation.primary_metric] + list(plan.validation.other_metrics)
    scoring = scorers_for(plan.problem_type.value, metric_names)

    # --- Train each recommended model on the SAME folds --- #
    for algo in plan.algorithms[:max_models]:
        result = ModelResult(
            name=algo.name,
            rank_requested=algo.rank,
            is_baseline=algo.is_baseline,
            primary_metric=plan.validation.primary_metric,
            primary_higher_is_better=plan.validation.primary_metric not in {"rmse", "mae"},
        )

        estimator = build_estimator(algo.sklearn_path, plan.problem_type.value)
        if estimator is None:
            result.failed = True
            result.error = f"Unrecognised algorithm path: {algo.sklearn_path}"
            report.results.append(result)
            continue

        preprocessor = build_preprocessor(
            numeric, categorical, scale_numeric=needs_scaling(algo.sklearn_path)
        )

        try:
            metrics, elapsed = evaluate_model(
                estimator, preprocessor, X, y, cv, scoring
            )
        except Exception as exc:  # keep the experiment going if one model fails
            result.failed = True
            result.error = str(exc)
            result.reasoning.append(
                "This model failed to train; the others were still evaluated."
            )
            report.results.append(result)
            continue

        for m_name, (mean, std) in metrics.items():
            result.metrics[m_name] = MetricScore(
                name=m_name,
                mean=mean,
                std=std,
                higher_is_better=m_name not in {"rmse", "mae"},
            )
        primary = result.metrics.get(plan.validation.primary_metric)
        if primary:
            result.primary_score = primary.mean
        result.train_seconds = elapsed
        result.reasoning.append(
            f"Trained with {used_folds}-fold cross-validation; "
            f"{plan.validation.primary_metric} = {result.primary_score:.4f}."
        )
        report.results.append(result)

    _choose_winner(report)
    _write_summary(report)
    return report


def _choose_winner(report: ExperimentReport) -> None:
    """Pick the best model by the primary metric and compare to the baseline."""
    ok = report.successful()
    if not ok:
        report.warnings.append("Every model failed to train; there is no winner.")
        return

    higher_better = ok[0].primary_higher_is_better
    winner = (max if higher_better else min)(ok, key=lambda r: r.primary_score)
    report.best_model = winner.name
    report.best_reasoning.append(
        f"'{winner.name}' achieved the best {report.primary_metric} "
        f"({winner.primary_score:.4f}) across the shared cross-validation folds."
    )

    # The signature DetaBeta lesson: did complexity actually pay off?
    baseline = next((r for r in ok if r.is_baseline), None)
    if baseline and winner.name != baseline.name:
        delta = winner.primary_score - baseline.primary_score
        improved = delta > 0 if higher_better else delta < 0
        if improved:
            report.beat_baseline = True
            report.baseline_comparison = (
                f"The winner beat the simple baseline ('{baseline.name}') by "
                f"{abs(delta):.4f} on {report.primary_metric}, so the extra "
                "complexity is justified here."
            )
        else:
            report.baseline_comparison = (
                f"No model beat the simple baseline ('{baseline.name}') on "
                f"{report.primary_metric}. Prefer the baseline: it is simpler, "
                "faster, and easier to explain for the same performance."
            )
            report.best_model = baseline.name
            report.best_reasoning.append(
                "Reassigned the recommendation to the baseline because added "
                "complexity did not improve the score."
            )
    elif baseline and winner.name == baseline.name:
        report.beat_baseline = False
        report.baseline_comparison = (
            "The simple baseline was already the best model -- a great outcome, "
            "since simpler models are cheaper and easier to trust."
        )


def _write_summary(report: ExperimentReport) -> None:
    """Compose a short, plain-language summary for the UI."""
    ok = report.successful()
    if not ok:
        report.summary = "No models could be trained, so no comparison is available."
        return

    parts = [
        f"Trained {len(ok)} model(s) on {report.n_rows_used} rows and "
        f"{report.n_features_used} feature(s) to predict '{report.target}'.",
        f"Best model: {report.best_model} "
        f"({report.primary_metric} = {report.best().primary_score:.4f}).",
    ]
    if report.baseline_comparison:
        parts.append(report.baseline_comparison)
    report.summary = " ".join(parts)
