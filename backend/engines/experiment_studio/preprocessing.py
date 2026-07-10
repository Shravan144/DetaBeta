"""
Preprocessing for Engine 7 (Experiment Studio).

The single most important idea here is **avoiding data leakage**. If we imputed
missing values or scaled columns using statistics from the WHOLE dataset before
splitting into train/test folds, information from the test fold would "leak"
into training and our scores would be dishonestly optimistic.

We prevent this by wrapping every step in a scikit-learn `Pipeline` /
`ColumnTransformer`. Inside cross-validation, scikit-learn re-fits the imputer,
scaler, and encoder on the *training portion of each fold only* -- exactly the
correct behaviour, done automatically.

We choose which transform applies to which column using the semantic types from
Engine 1 (not the raw pandas dtype), so meaning drives preprocessing.
"""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from engines.dataset_understanding.types import DatasetProfile, SemanticType

# Semantic types we feed to the model as numbers vs. as categories.
_NUMERIC_TYPES = {SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE}
_CATEGORICAL_TYPES = {SemanticType.CATEGORICAL, SemanticType.BINARY}


def split_feature_types(
    profile: DatasetProfile,
    feature_columns: list[str],
) -> tuple[list[str], list[str]]:
    """
    Split the chosen feature columns into (numeric, categorical) lists using
    Engine 1's semantic classification.

    Returns two lists of column names. Columns whose semantic type is neither
    clearly numeric nor categorical are skipped (Engine 6 already excluded IDs,
    text, and constants, so this is just a safety net).
    """
    numeric: list[str] = []
    categorical: list[str] = []

    for name in feature_columns:
        col = profile.column(name)
        if col is None:
            continue
        if col.semantic_type in _NUMERIC_TYPES:
            numeric.append(name)
        elif col.semantic_type in _CATEGORICAL_TYPES:
            categorical.append(name)
        # else: skip (unexpected here, but we fail safe rather than crash)

    return numeric, categorical


def _make_ohe() -> OneHotEncoder:
    """
    Build a OneHotEncoder that is robust across scikit-learn versions.

    `handle_unknown="ignore"` means a category seen only in a test fold won't
    crash prediction -- it just encodes as all-zeros. This is essential inside
    cross-validation.
    """
    # scikit-learn renamed `sparse` -> `sparse_output` in 1.2. Try the modern
    # keyword first and fall back so this works on older installs too.
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # pragma: no cover - only on very old sklearn
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_preprocessor(
    numeric: list[str],
    categorical: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    """
    Build a ColumnTransformer that preprocesses numeric and categorical columns.

    Numeric branch:  median-impute (robust to skew/outliers) then optionally
                     standard-scale (needed by Logistic/Linear Regression, not
                     by trees).
    Categorical branch: most-frequent-impute then one-hot encode.

    `scale_numeric` is toggled per-algorithm by the caller: linear/distance
    models need scaling; tree ensembles don't care, so we skip it for them to
    keep the pipeline honest about what each model actually requires.
    """
    numeric_steps: list[tuple[str, object]] = [
        ("impute", SimpleImputer(strategy="median")),
    ]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    numeric_pipe = Pipeline(numeric_steps)

    categorical_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", _make_ohe()),
        ]
    )

    transformers = []
    if numeric:
        transformers.append(("num", numeric_pipe, numeric))
    if categorical:
        transformers.append(("cat", categorical_pipe, categorical))

    # `remainder="drop"` guarantees only the columns we explicitly named reach
    # the model -- no accidental leakage of an unlisted column.
    return ColumnTransformer(transformers=transformers, remainder="drop")


def prepare_target(y: pd.Series) -> pd.Series:
    """
    Clean the target column before training.

    We drop rows where the target itself is missing (you cannot learn from a
    row with no answer), which the caller handles by aligning X to the same
    index. Here we just return y unchanged as a hook for future encoding
    (e.g. label-encoding string classes), keeping the pipeline readable.
    """
    return y
