"""
The recommendation detectors for the Feature Lab Engine (Engine 5).

Each function inspects the DatasetProfile from Engine 1 (semantic types + per
column stats) and returns zero or more FeatureRecommendation objects. Every
recommendation carries evidence (real numbers) and a teaching code snippet.

Design rules (consistent with Engines 1-4):
  - One function = one family of recommendation.
  - Pure inspection: we read the profile/DataFrame, we never modify data.
  - We reason from *meaning* (semantic type), not raw dtype.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding.types import DatasetProfile, SemanticType
from .types import FeatureRecommendation, Priority, TransformType


# Thresholds kept as named constants so the reasoning can quote them.
SKEW_LOG_THRESHOLD = 1.0        # |skew| above this = clearly tailed
SKEW_STRONG_THRESHOLD = 2.0     # very heavy tail -> log preferred over sqrt
ONE_HOT_MAX_CATEGORIES = 15     # above this, one-hot explodes the column count
RARE_CATEGORY_MAX_FREQ = 0.02   # a level seen in <2% of rows is "rare"
HIGH_CARDINALITY_MIN = 15       # many categories -> prefer frequency encoding
SCALE_RANGE_RATIO = 10.0        # if columns differ this much in spread, scale


# --- Numeric shape ------------------------------------------------------------

def suggest_skew_fixes(profile: DatasetProfile) -> list[FeatureRecommendation]:
    """
    Recommend a log or sqrt transform for heavily skewed numeric columns.

    WHY: many models (linear/logistic regression, distance-based methods)
    assume roughly symmetric inputs. A long right tail lets a few huge values
    dominate. log() and sqrt() compress large values and pull the tail in.
    """
    recs: list[FeatureRecommendation] = []
    for col in profile.columns_of_type(SemanticType.NUMERIC_CONTINUOUS):
        skew = float(col.stats.get("skew", 0.0))
        col_min = col.stats.get("min", None)
        if abs(skew) < SKEW_LOG_THRESHOLD:
            continue

        # log needs strictly positive values; if there are zeros/negatives we
        # either suggest log1p (for >= 0) or fall back to sqrt.
        can_log = isinstance(col_min, (int, float)) and col_min > 0
        can_log1p = isinstance(col_min, (int, float)) and col_min >= 0

        if skew >= SKEW_STRONG_THRESHOLD and (can_log or can_log1p):
            fn = "np.log" if can_log else "np.log1p"
            rec = FeatureRecommendation(
                transform=TransformType.LOG_TRANSFORM,
                columns=[col.name],
                priority=Priority.RECOMMENDED,
                title=f"Log-transform '{col.name}' to tame its heavy right tail",
                new_feature_hint=f"{col.name}_log",
                evidence={"skew": skew, "min": col_min},
                code_snippet=(
                    f"df['{col.name}_log'] = {fn}(df['{col.name}'])"
                ),
            )
            rec.add_reason(
                f"'{col.name}' has skew {skew:.2f} (>= {SKEW_STRONG_THRESHOLD}), "
                f"a strong right tail. A log transform compresses large values "
                f"so no single huge value dominates the model."
            )
            if not can_log and can_log1p:
                rec.add_reason(
                    "The column contains zeros, so we use log1p (log(1+x)) "
                    "instead of log(x), which is undefined at 0."
                )
            recs.append(rec)
        else:
            # Moderate skew, or values that block log -> gentler sqrt.
            can_sqrt = isinstance(col_min, (int, float)) and col_min >= 0
            if not can_sqrt:
                continue
            rec = FeatureRecommendation(
                transform=TransformType.SQRT_TRANSFORM,
                columns=[col.name],
                priority=Priority.OPTIONAL,
                title=f"Square-root transform '{col.name}' to reduce moderate skew",
                new_feature_hint=f"{col.name}_sqrt",
                evidence={"skew": skew, "min": col_min},
                code_snippet=f"df['{col.name}_sqrt'] = np.sqrt(df['{col.name}'])",
            )
            rec.add_reason(
                f"'{col.name}' has skew {skew:.2f} (>= {SKEW_LOG_THRESHOLD}), a "
                f"moderate tail. sqrt is a gentler fix than log and keeps zeros valid."
            )
            recs.append(rec)
    return recs


def suggest_scaling(profile: DatasetProfile) -> list[FeatureRecommendation]:
    """
    Recommend standardising numeric columns when they live on very different
    scales (e.g. age 0-100 vs income 0-500000).

    WHY: distance- and gradient-based models (KNN, SVM, k-means, neural nets,
    regularised regression) let large-magnitude columns dominate simply because
    their numbers are bigger. Scaling puts every column on comparable footing.
    """
    numeric_cols = [
        c for c in profile.columns
        if c.semantic_type in (
            SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE
        )
    ]
    # Need at least two numeric columns for "different scales" to matter.
    spreads = []
    for c in numeric_cols:
        std = c.stats.get("std", None)
        if isinstance(std, (int, float)) and std > 0:
            spreads.append((c.name, float(std)))
    if len(spreads) < 2:
        return []

    stds = [s for _, s in spreads]
    ratio = max(stds) / min(stds)
    if ratio < SCALE_RANGE_RATIO:
        return []

    names = [n for n, _ in spreads]
    rec = FeatureRecommendation(
        transform=TransformType.STANDARD_SCALE,
        columns=names,
        priority=Priority.RECOMMENDED,
        title="Standardise numeric columns (they live on very different scales)",
        evidence={
            "std_ratio": round(ratio, 1),
            "spreads": {n: round(s, 2) for n, s in spreads},
        },
        code_snippet=(
            "from sklearn.preprocessing import StandardScaler\n"
            f"cols = {names}\n"
            "df[cols] = StandardScaler().fit_transform(df[cols])"
        ),
    )
    rec.add_reason(
        f"The largest column spread is {ratio:.0f}x the smallest "
        f"(std ratio {ratio:.1f}). Distance- and gradient-based models would "
        f"let the wide-range columns dominate. StandardScaler rescales each to "
        f"mean 0, std 1 so they contribute fairly."
    )
    rec.warnings.append(
        "Tree-based models (Random Forest, XGBoost) do NOT need scaling; apply "
        "this mainly for KNN, SVM, k-means, neural nets and regularised models."
    )
    rec.warnings.append(
        "Fit the scaler on TRAIN data only, then apply to test -- otherwise you "
        "leak information from the test set."
    )
    return [rec]


def suggest_outlier_clipping(
    df: pd.DataFrame, profile: DatasetProfile
) -> list[FeatureRecommendation]:
    """
    Recommend clipping (winsorizing) columns with extreme outliers, as a
    milder alternative to deleting rows.

    WHY: a handful of extreme values can distort means, variances and model
    coefficients. Clipping caps them at a sensible percentile instead of
    throwing away whole rows (which loses the other columns' information).
    """
    recs: list[FeatureRecommendation] = []
    for col in profile.columns_of_type(SemanticType.NUMERIC_CONTINUOUS):
        series = pd.to_numeric(df[col.name], errors="coerce").dropna()
        if len(series) < 10:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((series < lo) | (series > hi)).sum())
        out_pct = n_out / len(series) * 100
        if out_pct < 1.0:
            continue
        rec = FeatureRecommendation(
            transform=TransformType.CLIP_OUTLIERS,
            columns=[col.name],
            priority=Priority.OPTIONAL,
            title=f"Clip extreme outliers in '{col.name}' instead of dropping rows",
            new_feature_hint=f"{col.name}_clipped",
            evidence={
                "outlier_count": n_out,
                "outlier_pct": round(out_pct, 1),
                "lower_bound": round(float(lo), 2),
                "upper_bound": round(float(hi), 2),
            },
            code_snippet=(
                f"lo, hi = df['{col.name}'].quantile([0.01, 0.99])\n"
                f"df['{col.name}_clipped'] = df['{col.name}'].clip(lo, hi)"
            ),
        )
        rec.add_reason(
            f"{n_out} value(s) ({out_pct:.1f}%) fall outside the IQR fence "
            f"[{lo:.1f}, {hi:.1f}]. Clipping caps them rather than deleting rows, "
            f"preserving the rest of each row's information."
        )
        rec.warnings.append(
            "Only clip if the extremes are errors or noise. Genuine rare events "
            "(fraud, spikes) may be exactly what you want the model to see."
        )
        recs.append(rec)
    return recs


# --- Categorical encoding -----------------------------------------------------

def suggest_categorical_encoding(
    df: pd.DataFrame, profile: DatasetProfile
) -> list[FeatureRecommendation]:
    """
    Recommend how to turn category labels into numbers.

    WHY: most models cannot consume the string "France" directly. The *right*
    encoding depends on how many categories there are:
        - few (<= 15)     -> one-hot (a 0/1 column per category)
        - many (> 15)     -> frequency encoding (avoid a column explosion)
    Binary columns get a simple 0/1 map.
    """
    recs: list[FeatureRecommendation] = []
    cats = profile.columns_of_type(SemanticType.CATEGORICAL)
    for col in cats:
        n_unique = col.n_unique
        if n_unique <= ONE_HOT_MAX_CATEGORIES:
            rec = FeatureRecommendation(
                transform=TransformType.ONE_HOT_ENCODE,
                columns=[col.name],
                priority=Priority.ESSENTIAL,
                title=f"One-hot encode '{col.name}' ({n_unique} categories)",
                evidence={"n_categories": n_unique},
                code_snippet=(
                    f"df = pd.get_dummies(df, columns=['{col.name}'], "
                    f"prefix='{col.name}')"
                ),
            )
            rec.add_reason(
                f"'{col.name}' has {n_unique} unordered labels (<= "
                f"{ONE_HOT_MAX_CATEGORIES}). One-hot encoding makes one 0/1 "
                f"column per label so the model treats them as distinct, with "
                f"no fake ordering between them."
            )
        else:
            rec = FeatureRecommendation(
                transform=TransformType.FREQUENCY_ENCODE,
                columns=[col.name],
                priority=Priority.RECOMMENDED,
                title=f"Frequency-encode '{col.name}' ({n_unique} categories)",
                new_feature_hint=f"{col.name}_freq",
                evidence={"n_categories": n_unique},
                code_snippet=(
                    f"freq = df['{col.name}'].value_counts(normalize=True)\n"
                    f"df['{col.name}_freq'] = df['{col.name}'].map(freq)"
                ),
            )
            rec.add_reason(
                f"'{col.name}' has {n_unique} labels (> {ONE_HOT_MAX_CATEGORIES}). "
                f"One-hot would explode into {n_unique} sparse columns and invite "
                f"overfitting, so we encode each label by how common it is instead."
            )
            rec.warnings.append(
                "Frequency encoding loses identity (two equally-common labels get "
                "the same number). Consider target encoding if a target exists."
            )
        recs.append(rec)

    # Binary columns: a clean 0/1 mapping.
    for col in profile.columns_of_type(SemanticType.BINARY):
        # Skip if it already looks like 0/1 numbers.
        sample = [str(v).lower() for v in col.sample_values[:5]]
        already_numeric = all(s in ("0", "1", "0.0", "1.0") for s in sample if s)
        if already_numeric:
            continue
        rec = FeatureRecommendation(
            transform=TransformType.ORDINAL_ENCODE,
            columns=[col.name],
            priority=Priority.ESSENTIAL,
            title=f"Map binary column '{col.name}' to 0/1",
            evidence={"n_categories": col.n_unique},
            code_snippet=(
                f"df['{col.name}'] = df['{col.name}'].map("
                f"{{label_a: 0, label_b: 1}})  # fill in your two labels"
            ),
        )
        rec.add_reason(
            f"'{col.name}' has exactly two values, so a single 0/1 column "
            f"captures it fully -- no need for two one-hot columns."
        )
        recs.append(rec)
    return recs


def suggest_group_rare_categories(
    df: pd.DataFrame, profile: DatasetProfile
) -> list[FeatureRecommendation]:
    """
    Recommend folding very rare category levels into a single "Other" bucket.

    WHY: a label that appears once or twice gives the model almost nothing to
    learn and can cause train/test mismatches (a category present in test but
    never in train). Grouping them stabilises the feature.
    """
    recs: list[FeatureRecommendation] = []
    n_rows = len(df)
    if n_rows == 0:
        return recs
    for col in profile.columns_of_type(SemanticType.CATEGORICAL):
        counts = df[col.name].value_counts(dropna=True)
        freq = counts / n_rows
        rare = freq[freq < RARE_CATEGORY_MAX_FREQ]
        if len(rare) < 2:
            continue
        rec = FeatureRecommendation(
            transform=TransformType.GROUP_RARE_CATEGORIES,
            columns=[col.name],
            priority=Priority.OPTIONAL,
            title=f"Group {len(rare)} rare labels in '{col.name}' into 'Other'",
            evidence={
                "rare_label_count": int(len(rare)),
                "threshold_pct": RARE_CATEGORY_MAX_FREQ * 100,
                "examples": [str(x) for x in rare.index[:5]],
            },
            code_snippet=(
                f"freq = df['{col.name}'].value_counts(normalize=True)\n"
                f"rare = freq[freq < {RARE_CATEGORY_MAX_FREQ}].index\n"
                f"df['{col.name}'] = df['{col.name}'].replace(rare, 'Other')"
            ),
        )
        rec.add_reason(
            f"{len(rare)} label(s) each appear in under "
            f"{RARE_CATEGORY_MAX_FREQ*100:.0f}% of rows. Folding them into "
            f"'Other' avoids near-empty one-hot columns and train/test mismatches."
        )
        recs.append(rec)
    return recs


# --- Datetime -----------------------------------------------------------------

def suggest_datetime_parts(profile: DatasetProfile) -> list[FeatureRecommendation]:
    """
    Recommend decomposing datetime columns into usable parts.

    WHY: a raw timestamp is nearly useless to a model, but the *parts* carry
    real signal -- day of week (weekday vs weekend), month (seasonality), hour
    (time of day). Extracting them turns one dead column into several live ones.
    """
    recs: list[FeatureRecommendation] = []
    for col in profile.columns_of_type(SemanticType.DATETIME):
        rec = FeatureRecommendation(
            transform=TransformType.EXTRACT_DATETIME_PARTS,
            columns=[col.name],
            priority=Priority.RECOMMENDED,
            title=f"Extract calendar parts from '{col.name}'",
            new_feature_hint=f"{col.name}_year / _month / _dayofweek",
            evidence={},
            code_snippet=(
                f"dt = pd.to_datetime(df['{col.name}'])\n"
                f"df['{col.name}_year'] = dt.dt.year\n"
                f"df['{col.name}_month'] = dt.dt.month\n"
                f"df['{col.name}_dayofweek'] = dt.dt.dayofweek\n"
                f"df['{col.name}_is_weekend'] = dt.dt.dayofweek >= 5"
            ),
        )
        rec.add_reason(
            f"'{col.name}' is a datetime. Models can't use a raw timestamp, but "
            f"year/month/day-of-week expose seasonality and weekly patterns the "
            f"model can actually learn from."
        )
        recs.append(rec)
    return recs


# --- Structural cleanups for modelling ---------------------------------------

def suggest_drops(profile: DatasetProfile) -> list[FeatureRecommendation]:
    """
    Recommend dropping columns that hurt or can't help a model:
    identifiers (leakage / noise), constants (zero information) and free text
    (needs separate NLP handling before it's model-ready).
    """
    recs: list[FeatureRecommendation] = []

    for col in profile.columns_of_type(SemanticType.IDENTIFIER):
        rec = FeatureRecommendation(
            transform=TransformType.DROP_COLUMN,
            columns=[col.name],
            priority=Priority.ESSENTIAL,
            title=f"Drop identifier '{col.name}' before modelling",
            evidence={"unique_pct": col.unique_pct},
            code_snippet=f"df = df.drop(columns=['{col.name}'])",
        )
        rec.add_reason(
            f"'{col.name}' is an identifier ({col.unique_pct:.0f}% unique). It "
            f"carries no generalisable signal and can cause leakage or let a "
            f"model 'memorise' rows. Remove it from the feature set."
        )
        recs.append(rec)

    for col in profile.columns_of_type(SemanticType.CONSTANT):
        rec = FeatureRecommendation(
            transform=TransformType.DROP_COLUMN,
            columns=[col.name],
            priority=Priority.ESSENTIAL,
            title=f"Drop constant column '{col.name}'",
            evidence={"n_unique": col.n_unique},
            code_snippet=f"df = df.drop(columns=['{col.name}'])",
        )
        rec.add_reason(
            f"'{col.name}' has a single repeated value, so it has zero variance "
            f"and cannot help a model distinguish rows."
        )
        recs.append(rec)

    for col in profile.columns_of_type(SemanticType.TEXT):
        rec = FeatureRecommendation(
            transform=TransformType.TEXT_FEATURE,
            columns=[col.name],
            priority=Priority.OPTIONAL,
            title=f"Handle free-text column '{col.name}' with NLP features",
            evidence={"avg_char_length": col.stats.get("avg_char_length")},
            code_snippet=(
                "from sklearn.feature_extraction.text import TfidfVectorizer\n"
                f"tfidf = TfidfVectorizer(max_features=100)\n"
                f"X_text = tfidf.fit_transform(df['{col.name}'].fillna(''))"
            ),
        )
        rec.add_reason(
            f"'{col.name}' is free text with many unique values. It can't be "
            f"one-hot encoded; it needs NLP features (e.g. TF-IDF) or should be "
            f"set aside for modelling."
        )
        recs.append(rec)

    return recs
