"""
Engine 8 orchestrator: Explainability.

Answers: "Why did the model predict this?"

Flow:
  1. Ask Engine 6 for the plan and Engine 7 for the experiment (or accept them
     pre-computed to avoid recomputation).
  2. Rebuild the WINNING model exactly as Engine 7 trained it (same estimator,
     same leak-free preprocessing pipeline) and fit it on all usable rows.
  3. GLOBAL: permutation importance -> which features matter most overall.
  4. LOCAL: pick a few example rows and explain each prediction with occlusion.
  5. Translate every number into plain language.

Note on honesty: for explanation we fit on the full dataset because the goal is
to understand the model's behaviour, not to estimate performance (Engine 7
already did that with cross-validation). We say so in a warning.
"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import confusion_matrix, get_scorer
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline

from engines.dataset_understanding import understand_dataset
from engines.ml_recommendation import recommend_model
from engines.ml_recommendation.types import MLRecommendationReport, ProblemType
from engines.experiment_studio.engine import run_experiment
from engines.experiment_studio.preprocessing import build_preprocessor, split_feature_types
from engines.experiment_studio.trainer import (
    build_estimator,
    make_cv,
    needs_scaling,
    scorers_for,
)
from engines.experiment_studio.types import ExperimentReport

from .explainers import permutation_importance_by_column, shapley_contributions
from .types import (
    ConfusionMatrix,
    ExplainabilityReport,
    FeatureContribution,
    FeatureImportance,
    PredictionExplanation,
)


def explain_model(
    df: pd.DataFrame,
    target: str,
    plan: MLRecommendationReport | None = None,
    experiment: ExperimentReport | None = None,
    n_examples: int = 3,
) -> ExplainabilityReport:
    """
    Explain the winning model from Engine 7 for `target`.

    `plan` and `experiment` are optional: pass them in to reuse Engines 6/7's
    work; otherwise this function runs them.
    """
    if plan is None:
        plan = recommend_model(df, target=target)
    if experiment is None:
        experiment = run_experiment(df, target=target, plan=plan)

    report = ExplainabilityReport(
        target=target,
        model_name=experiment.best_model,
        problem_type=plan.problem_type.value,
        primary_metric=experiment.primary_metric,
    )

    # --- Guards --- #
    if not experiment.best_model or not experiment.successful():
        report.warnings.append(
            "Engine 7 produced no successful model, so there is nothing to explain."
        )
        report.summary = "No model was available to explain."
        return report

    if plan.problem_type == ProblemType.UNKNOWN or not plan.feature_columns:
        report.warnings.append("No usable modelling plan, so explanation was skipped.")
        report.summary = "No model was available to explain."
        return report

    # --- Rebuild the winning model exactly as Engine 7 did --- #
    winner = experiment.best()
    algo = next((a for a in plan.algorithms if a.name == winner.name), None)
    if algo is None:
        report.warnings.append(
            f"Could not locate the winning algorithm '{winner.name}' in the plan."
        )
        report.summary = "The winning model could not be rebuilt for explanation."
        return report

    work = df[df[target].notna()].copy()
    
    # --- Subsample if too large for responsive interactive explainability --- #
    max_rows = 2000
    if len(work) > max_rows:
        work = work.sample(n=max_rows, random_state=42)
        report.warnings.append(
            f"The dataset is large ({len(df)} rows). Subsampled {max_rows} rows for explainability calculations."
        )

    y = work[target]
    profile = understand_dataset(work)
    numeric, categorical = split_feature_types(profile, plan.feature_columns)
    feature_cols = numeric + categorical
    X = work[feature_cols]

    estimator = build_estimator(algo.sklearn_path, plan.problem_type.value)
    preprocessor = build_preprocessor(
        numeric, categorical, scale_numeric=needs_scaling(algo.sklearn_path)
    )
    pipe = Pipeline([("prep", preprocessor), ("model", estimator)])
    pipe.fit(X, y)

    report.warnings.append(
        "Explanations are computed on the full dataset to understand the model's "
        "behaviour; performance was already measured honestly by Engine 7 with "
        "cross-validation."
    )

    is_classification = "classification" in plan.problem_type.value

    # --- GLOBAL importance (permutation) --- #
    scorer = _pick_scorer(experiment.primary_metric, is_classification)
    report.base_score = float(scorer(pipe, X, y))
    raw_imp = permutation_importance_by_column(
        pipe, X, y, scorer, feature_cols, n_repeats=5
    )
    _fill_global_importances(report, raw_imp)

    # --- Where does the model make mistakes? (confusion matrix) --- #
    if is_classification:
        report.confusion = _confusion_matrix(
            pipe, X, y, plan.problem_type.value, report
        )

    # --- LOCAL explanations for a few example rows (Shapley values) --- #
    positive_class = _positive_class(y) if is_classification else None
    # A background sample is the "reference" distribution Shapley values are
    # measured against. Cap it so the sampling stays fast.
    background = X if len(X) <= 100 else X.sample(n=100, random_state=42)
    example_indices = list(X.index[:n_examples])
    for idx in example_indices:
        explanation = _explain_row(
            pipe, background, X, idx, feature_cols, is_classification, positive_class
        )
        report.examples.append(explanation)

    _write_summary(report)
    return report


def _confusion_matrix(
    pipe,
    X: pd.DataFrame,
    y: pd.Series,
    problem_type: str,
    report: ExplainabilityReport,
) -> ConfusionMatrix | None:
    """Cross-validated confusion matrix so 'where it errs' uses real numbers.

    We use out-of-fold predictions (`cross_val_predict`) rather than predictions
    on the training data, so the mistakes shown are honest generalization errors
    consistent with Engine 7's scoring.
    """
    try:
        cv, _ = make_cv(problem_type, n_folds=5, stratify=True, y=y)
        y_pred = cross_val_predict(pipe, X, y, cv=cv)
    except Exception as exc:  # noqa: BLE001 - explainability must never crash
        report.warnings.append(f"Could not compute the confusion matrix: {exc}")
        return None

    labels = sorted(y.unique(), key=lambda v: str(v))
    is_binary = len(labels) == 2

    # For binary, order labels as [negative, positive] so the 2x2 lines up with
    # the classic TN/FP/FN/TP layout.
    positive_label = _positive_class(y) if is_binary else None
    if is_binary:
        negative_label = next(l for l in labels if l != positive_label)
        labels = [negative_label, positive_label]

    matrix = confusion_matrix(y, y_pred, labels=labels)
    total = int(matrix.sum())
    correct = int(matrix.trace())

    cm = ConfusionMatrix(
        labels=[_native(l) for l in labels],
        matrix=[[int(c) for c in row] for row in matrix],
        accuracy=(correct / total) if total else 0.0,
        n_samples=total,
        is_binary=is_binary,
    )

    if is_binary:
        # matrix rows/cols are [negative, positive].
        cm.true_negative = int(matrix[0][0])
        cm.false_positive = int(matrix[0][1])
        cm.false_negative = int(matrix[1][0])
        cm.true_positive = int(matrix[1][1])
        cm.positive_label = _native(positive_label)
        cm.negative_label = _native(labels[0])
        cm.note = (
            f"Out-of-fold predictions treating '{cm.positive_label}' as the "
            "positive class."
        )
    else:
        cm.note = "Out-of-fold predictions across all classes."

    return cm


def _native(value):
    """Convert numpy scalar labels to plain Python for clean JSON."""
    return getattr(value, "item", lambda: value)()


def _pick_scorer(metric: str, is_classification: bool):
    """Choose a scikit-learn scorer callable for permutation importance."""
    table = scorers_for(
        "classification" if is_classification else "regression", [metric]
    )
    sklearn_name = table.get(metric)
    if sklearn_name is None:
        sklearn_name = "accuracy" if is_classification else "r2"
    return get_scorer(sklearn_name)


def _positive_class(y: pd.Series):
    """
    Pick the 'positive' class to explain toward. For binary targets we use the
    rarer class (usually the event of interest, e.g. survived=1, churn=yes).
    """
    counts = y.value_counts()
    if len(counts) == 2:
        return counts.idxmin()
    return counts.idxmax()  # multiclass: explain toward the most common class


def _fill_global_importances(report: ExplainabilityReport, raw_imp: dict) -> None:
    """Convert raw importance numbers into sorted, interpreted objects."""
    # Only positive importances contribute to the "share of signal" total.
    total = sum(max(0.0, mean) for mean, _ in raw_imp.values()) or 1.0

    items: list[FeatureImportance] = []
    for feature, (mean, std) in raw_imp.items():
        share = max(0.0, mean) / total
        if mean <= 0.0001:
            reasoning = (
                f"Shuffling '{feature}' did not hurt the model, so it relied "
                "little on this feature (it may be redundant or uninformative)."
            )
        else:
            reasoning = (
                f"Shuffling '{feature}' dropped the {report.primary_metric} by "
                f"{mean:.4f} on average, about {share:.0%} of the model's total "
                "reliance -- the model leans on this feature."
            )
        items.append(
            FeatureImportance(
                feature=feature,
                importance=mean,
                std=std,
                share=share,
                reasoning=reasoning,
            )
        )

    items.sort(key=lambda fi: fi.importance, reverse=True)
    report.global_importances = items


def _explain_row(
    pipe,
    background: pd.DataFrame,
    X: pd.DataFrame,
    idx: int,
    feature_cols: list[str],
    is_classification: bool,
    positive_class,
) -> PredictionExplanation:
    """Build a local explanation for a single row via Shapley values."""
    actual, baseline, contribs = shapley_contributions(
        pipe, X, idx, background, feature_cols, positive_class=positive_class
    )

    predicted_label = pipe.predict(X.loc[[idx]])[0]
    probability = None
    if is_classification and hasattr(pipe, "predict_proba"):
        probability = actual  # already the positive-class probability

    explanation = PredictionExplanation(
        row_index=int(idx),
        predicted_label=predicted_label,
        predicted_probability=probability,
        baseline_prediction=baseline,
        method="shapley",
    )

    contributions: list[FeatureContribution] = []
    for feature, (value, effect) in contribs.items():
        if effect > 0.0001:
            direction = "increases"
        elif effect < -0.0001:
            direction = "decreases"
        else:
            direction = "no effect"

        if direction == "no effect":
            reasoning = f"'{feature}' = {value!r} had almost no effect on this prediction."
        else:
            reasoning = (
                f"'{feature}' = {value!r} {direction} the prediction "
                f"(Shapley value {effect:+.4f}) relative to the average prediction."
            )
        contributions.append(
            FeatureContribution(
                feature=feature,
                value=value,
                effect=effect,
                direction=direction,
                reasoning=reasoning,
            )
        )

    contributions.sort(key=lambda c: abs(c.effect), reverse=True)
    explanation.contributions = contributions

    top = contributions[0] if contributions else None
    if top and top.direction != "no effect":
        explanation.summary = (
            f"Predicted {predicted_label!r}. The biggest driver was "
            f"'{top.feature}' = {top.value!r}, which {top.direction} the prediction."
        )
    else:
        explanation.summary = (
            f"Predicted {predicted_label!r}. No single feature dominated this row."
        )
    return explanation


def _write_summary(report: ExplainabilityReport) -> None:
    """Compose a short, plain-language summary for the UI."""
    if not report.global_importances:
        report.summary = "The model could be fit but produced no usable explanations."
        return

    top = report.top_features(3)
    named = ", ".join(f"'{fi.feature}'" for fi in top if fi.importance > 0.0001)
    if named:
        report.summary = (
            f"The {report.model_name} relies most on {named} to predict "
            f"'{report.target}'. Explanations below show both the model's overall "
            "priorities and why it made specific example predictions."
        )
    else:
        report.summary = (
            f"No feature strongly drove the {report.model_name}; predictions may be "
            "close to the base rate. Consider revisiting features in the Feature Lab."
        )
