"""
The explainability techniques for Engine 8.

We implement transparent, model-agnostic techniques from scratch rather than
pulling in a heavy black-box dependency. The logic stays readable and teaches
the actual math:

  GLOBAL -- permutation importance
    Train the model, measure its score. Then, one feature at a time, randomly
    shuffle that feature's column and re-score. If the score collapses, the
    model depended heavily on that feature. If nothing changes, the feature was
    (to this model) useless. We repeat the shuffle several times and average,
    because a single shuffle is noisy.

  LOCAL -- Shapley values (the method SHAP is built on)
    For one specific row, fairly attribute the gap between the model's
    prediction and its average (baseline) prediction across the features. We
    approximate the exact (exponential-cost) Shapley values with Monte-Carlo
    coalition sampling: reveal the row's real feature values one at a time in
    random orders, starting from a random reference row, and credit each feature
    with the prediction jump it causes. See `shapley_contributions` for details.
    The contributions sum to (prediction - baseline), SHAP's efficiency property.

  LOCAL (legacy) -- occlusion / what-if
    A simpler single-pass alternative kept for reference: replace each value
    with the dataset's typical value and see how far the prediction moves.

All techniques work on the ORIGINAL columns (we perturb the raw dataframe and
let the model's own preprocessing pipeline transform it), so explanations are
stated in human terms, never in one-hot-encoded feature names.
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
    return float(_prediction_scalar_batch(estimator, row_df, positive_class)[0])


def _prediction_scalar_batch(estimator, X: pd.DataFrame, positive_class) -> np.ndarray:
    """
    Vectorized version of `_prediction_scalar`: one comparable number per row.

    Doing this in a single call (instead of row-by-row) is what makes the
    Shapley sampling below fast enough to be interactive.
    """
    if hasattr(estimator, "predict_proba") and positive_class is not None:
        proba = estimator.predict_proba(X)
        classes = list(estimator.classes_)
        idx = classes.index(positive_class)
        return proba[:, idx].astype(float)
    preds = estimator.predict(X)
    if positive_class is not None:
        return (np.asarray(preds) == positive_class).astype(float)
    return np.asarray(preds, dtype=float)


def shapley_contributions(
    estimator,
    X: pd.DataFrame,
    row_index: int,
    background: pd.DataFrame,
    columns: list[str],
    positive_class=None,
    n_samples: int = 40,
    random_state: int = 42,
) -> tuple[float, float, dict[str, tuple[object, float]]]:
    """
    Explain ONE row with SHAP-style Shapley values, computed from scratch.

    THE IDEA (the math SHAP is built on)
    ------------------------------------
    A prediction is a "game" and the features are "players" cooperating to move
    the prediction away from a baseline. A feature's Shapley value is its FAIR
    share of that movement, averaged over every possible order in which features
    could join the coalition.

    Trying every order is 2^n work, so we APPROXIMATE with Monte-Carlo sampling
    (the classic Strumbelj-Kononenko method):

      repeat n_samples times:
        * pick a random reference row from the background data
        * pick a random order of the features
        * start from the reference prediction, then reveal the instance's real
          features one at a time in that order; each feature's marginal push on
          the prediction is credited to it
      average each feature's credited push over all samples.

    This satisfies SHAP's key *efficiency* property: the contributions sum to
    (prediction - baseline), so the waterfall actually adds up.

    `X` supplies the instance row (via `row_index`) and its column dtypes;
    `background` is the reference pool the contributions are measured against.

    Returns (actual_prediction, baseline_prediction, contributions) where
    contributions maps column -> (actual_value, shapley_value), matching the
    shape the occlusion method returned so the rest of the engine is unchanged.
    """
    rng = np.random.default_rng(random_state)
    cols = list(columns)

    x_row = X.loc[row_index]
    row_df = X.loc[[row_index]]
    actual_pred = _prediction_scalar(estimator, row_df, positive_class)

    n_bg = len(background)
    phi = {c: 0.0 for c in cols}
    # We accumulate the prediction of each sampled reference. Because every
    # permutation telescopes exactly to (prediction - reference_prediction),
    # defining the baseline as the mean of THESE references makes the
    # efficiency property hold exactly: baseline + sum(phi) == prediction.
    ref_pred_sum = 0.0

    for _ in range(n_samples):
        # A random reference instance to "start" the coalition from.
        ref_pos = int(rng.integers(n_bg))
        ref = background.iloc[[ref_pos]]

        perm = list(rng.permutation(cols))

        # Build k+1 rows: row j has the first j features (in this order) set to
        # the instance's real values, the rest still at the reference's values.
        coalition = pd.concat([ref] * (len(perm) + 1), ignore_index=True)
        for i, col in enumerate(perm):
            # Cumulative: from step i+1 onward, feature `col` is "revealed".
            coalition.loc[i + 1 :, col] = x_row[col]

        preds = _prediction_scalar_batch(estimator, coalition, positive_class)
        ref_pred_sum += float(preds[0])  # coalition[0] is the pure reference
        # The jump when each feature is revealed is that feature's marginal push.
        for i, col in enumerate(perm):
            phi[col] += float(preds[i + 1] - preds[i])

    baseline_pred = ref_pred_sum / n_samples if n_samples else actual_pred

    contributions: dict[str, tuple[object, float]] = {}
    for col in cols:
        contributions[col] = (x_row[col], phi[col] / n_samples)

    return actual_pred, baseline_pred, contributions


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
