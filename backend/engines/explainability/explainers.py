"""
The explainability techniques for Engine 8.

We deliberately use two transparent, model-agnostic methods instead of a heavy
black-box dependency like SHAP. They teach the same core ideas and their logic
is easy to read:

  GLOBAL -- permutation importance
    Train the model, measure its score. Then, one feature at a time, randomly
    shuffle that feature's column and re-score. If the score collapses, the
    model depended heavily on that feature. If nothing changes, the feature was
    (to this model) useless. We repeat the shuffle several times and average,
    because a single shuffle is noisy.

  LOCAL -- occlusion / what-if
    For one specific row, get the model's prediction. Then, one feature at a
    time, replace that row's value with the dataset's "typical" value (median
    for numbers, mode for categories) and predict again. The change in the
    prediction is how much that feature's actual value mattered FOR THIS ROW.

Both work on the ORIGINAL columns (we perturb the raw dataframe and let the
model's own preprocessing pipeline transform it), so explanations are stated in
human terms, never in one-hot-encoded feature names.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _score(estimator, X: pd.DataFrame, y: pd.Series, scorer) -> float:
    """Score the fitted estimator on (X, y) with a single scorer callable."""
    return float(scorer(estimator, X, y))


def permutation_importance_by_column(
    estimator,
    X: pd.DataFrame,
    y: pd.Series,
    scorer,
    columns: list[str],
    n_repeats: int = 5,
    random_state: int = 42,
) -> dict[str, tuple[float, float]]:
    """
    Compute permutation importance for each ORIGINAL column.

    Returns {column: (mean_importance, std)} where importance is the average
    drop in score caused by shuffling that column. We implement it by hand
    (rather than sklearn.inspection.permutation_importance) so it operates on
    the original columns and the logic stays visible for learning.
    """
    rng = np.random.default_rng(random_state)
    base = _score(estimator, X, y, scorer)

    out: dict[str, tuple[float, float]] = {}
    for col in columns:
        drops: list[float] = []
        original = X[col].to_numpy(copy=True)
        for _ in range(n_repeats):
            shuffled = original.copy()
            rng.shuffle(shuffled)
            X_perturbed = X.copy()
            X_perturbed[col] = shuffled
            permuted_score = _score(estimator, X_perturbed, y, scorer)
            # A drop (base - permuted) means the feature helped the model.
            drops.append(base - permuted_score)
        out[col] = (float(np.mean(drops)), float(np.std(drops)))
    return out


def _typical_value(series: pd.Series):
    """The dataset's 'typical' value: median for numbers, mode otherwise."""
    if pd.api.types.is_numeric_dtype(series):
        return series.median()
    mode = series.mode(dropna=True)
    return mode.iloc[0] if not mode.empty else series.iloc[0]


def _prediction_scalar(estimator, row_df: pd.DataFrame, positive_class) -> float:
    """
    Turn a model's prediction for one row into a single comparable number.

    - Classification with probabilities: probability of the positive class.
    - Classification without probabilities: 1.0/0.0 for the predicted class.
    - Regression: the predicted value itself.
    """
    if hasattr(estimator, "predict_proba") and positive_class is not None:
        proba = estimator.predict_proba(row_df)[0]
        classes = list(estimator.classes_)
        idx = classes.index(positive_class)
        return float(proba[idx])
    pred = estimator.predict(row_df)[0]
    if positive_class is not None:
        return 1.0 if pred == positive_class else 0.0
    return float(pred)


def occlusion_contributions(
    estimator,
    X: pd.DataFrame,
    row_index: int,
    columns: list[str],
    positive_class=None,
) -> tuple[float, float, dict[str, tuple[object, float]]]:
    """
    Explain ONE row by the occlusion / what-if method.

    Returns (actual_prediction, baseline_prediction, contributions) where
    contributions maps column -> (actual_value, effect). `effect` is
    actual_prediction_with_real_value minus prediction_with_typical_value: how
    much this row's actual value moved the prediction relative to "typical".
    """
    row_df = X.loc[[row_index]]
    actual_pred = _prediction_scalar(estimator, row_df, positive_class)

    # Baseline = predict on a row made entirely of "typical" values.
    typical_row = row_df.copy()
    for col in X.columns:
        typical_row[col] = _typical_value(X[col])
    baseline_pred = _prediction_scalar(estimator, typical_row, positive_class)

    contributions: dict[str, tuple[object, float]] = {}
    for col in columns:
        probe = row_df.copy()
        probe[col] = _typical_value(X[col])
        pred_without = _prediction_scalar(estimator, probe, positive_class)
        # If removing the real value drops the prediction, the real value was
        # pushing it up (positive effect), and vice versa.
        effect = actual_pred - pred_without
        contributions[col] = (row_df[col].iloc[0], float(effect))

    return actual_pred, baseline_pred, contributions
