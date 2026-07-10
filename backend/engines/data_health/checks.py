"""
The individual health checks that power Engine 2.

Each function here answers a narrow question ("are there missing values?",
"are there duplicate rows?", "are there outliers?") and returns a list of
HealthIssue objects. The orchestrator in engine.py runs them all.

Design rules for every check:
  - It reads facts, it never modifies the DataFrame.
  - Every issue it raises carries EVIDENCE (numbers) and a RECOMMENDATION
    with REASONING. No bare "this is bad" flags.
  - It uses Engine 1's semantic types so recommendations fit the *meaning*
    of a column, not just its dtype. (e.g. we recommend the MEDIAN for a
    skewed continuous column, but the MODE for a category.)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.dataset_understanding.types import DatasetProfile, SemanticType

from .types import HealthIssue, IssueCategory, Severity


# ---------------------------------------------------------------------------
# 1. MISSING VALUES
# ---------------------------------------------------------------------------
def check_missing_values(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag columns with missing values and recommend a handling strategy.

    Why missingness matters: most statistical tests and ML models cannot
    handle NaNs at all, and *how* you fill them changes your results. The
    right fix depends on how much is missing AND what the column means.
    """
    issues: list[HealthIssue] = []

    for col in profile.columns:
        if col.n_missing == 0:
            continue

        pct = col.missing_pct

        # Severity scales with how much is missing. These thresholds are a
        # pragmatic convention, not a law -- and we tell the user that.
        if pct >= 60:
            severity = Severity.CRITICAL
        elif pct >= 30:
            severity = Severity.HIGH
        elif pct >= 5:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        issue = HealthIssue(
            category=IssueCategory.MISSING,
            severity=severity,
            column=col.name,
            title=f"'{col.name}' has {pct}% missing values",
            evidence={
                "n_missing": col.n_missing,
                "n_total": col.n_total,
                "missing_pct": pct,
                "semantic_type": col.semantic_type.value,
            },
        )

        # Recommendation depends on severity first...
        if severity == Severity.CRITICAL:
            issue.recommendation = f"Consider dropping the column '{col.name}'."
            issue.add_reason(
                f"With {pct}% of values missing, there is too little real data "
                f"to impute reliably -- any fill would be mostly invention."
            )
        else:
            # ...then on the column's MEANING (this is why Engine 1 came first).
            if col.semantic_type == SemanticType.NUMERIC_CONTINUOUS:
                # Choose mean vs median based on skew, because the mean is
                # dragged around by outliers while the median is robust.
                skew = col.stats.get("skew")
                if skew is not None and abs(skew) > 1:
                    issue.recommendation = f"Impute '{col.name}' with the MEDIAN."
                    issue.add_reason(
                        f"The column is skewed (skew={skew}), so the mean would be "
                        f"pulled toward the tail. The median is robust to that."
                    )
                else:
                    issue.recommendation = f"Impute '{col.name}' with the MEAN or MEDIAN."
                    issue.add_reason(
                        "The column is roughly symmetric, so mean and median are "
                        "both reasonable; median is the safer default."
                    )
            elif col.semantic_type in (
                SemanticType.CATEGORICAL,
                SemanticType.BINARY,
            ):
                issue.recommendation = (
                    f"Impute '{col.name}' with the most frequent category, or add "
                    f"an explicit 'Missing' category."
                )
                issue.add_reason(
                    "For categories there is no average, so we fill with the mode "
                    "or treat 'missing' as its own meaningful label."
                )
            elif col.semantic_type == SemanticType.NUMERIC_DISCRETE:
                issue.recommendation = f"Impute '{col.name}' with the MODE (most common count)."
                issue.add_reason(
                    "Discrete counts should stay whole numbers, so the mode keeps "
                    "the imputed values valid."
                )
            else:
                issue.recommendation = f"Review '{col.name}' manually before filling."
                issue.add_reason(
                    "This column's type does not have an obvious default fill; a "
                    "human should decide."
                )

        # A universal caveat that reinforces the "recommend, don't force" ethos.
        issue.add_reason(
            "We do not fill anything automatically -- imputation changes your data, "
            "so it should be a deliberate choice."
        )
        issues.append(issue)

    return issues


# ---------------------------------------------------------------------------
# 2. DUPLICATE ROWS
# ---------------------------------------------------------------------------
def check_duplicate_rows(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag fully-duplicated rows.

    Why it matters: duplicate rows secretly over-weight some observations,
    inflating confidence and biasing both statistics and models.
    """
    n_dupes = profile.n_duplicate_rows
    if n_dupes == 0:
        return []

    pct = round(n_dupes / profile.n_rows * 100, 2) if profile.n_rows else 0.0
    severity = Severity.HIGH if pct >= 10 else Severity.MEDIUM

    issue = HealthIssue(
        category=IssueCategory.DUPLICATES,
        severity=severity,
        column=None,
        title=f"{n_dupes} duplicate row(s) detected ({pct}% of the data)",
        evidence={"n_duplicate_rows": n_dupes, "duplicate_pct": pct},
        recommendation="Review the duplicates; drop them unless they are legitimately repeated records.",
    )
    issue.add_reason(
        "Identical rows count an observation more than once, which inflates "
        "sample size and can make patterns look stronger than they are."
    )
    issue.add_reason(
        "Sometimes duplicates are real (e.g. two identical transactions), so we "
        "recommend reviewing rather than blindly deleting."
    )
    return [issue]


# ---------------------------------------------------------------------------
# 3. CONSTANT COLUMNS
# ---------------------------------------------------------------------------
def check_constant_columns(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag columns that never change (a single value for every row).

    Why it matters: a column with one value has zero variance, so it cannot
    explain or predict anything. It just adds noise and cost.
    """
    issues: list[HealthIssue] = []
    for col in profile.columns_of_type(SemanticType.CONSTANT):
        issue = HealthIssue(
            category=IssueCategory.CONSTANT,
            severity=Severity.MEDIUM,
            column=col.name,
            title=f"'{col.name}' is constant (only one value)",
            evidence={"n_unique": col.n_unique, "sample_values": col.sample_values[:3]},
            recommendation=f"Drop '{col.name}'.",
        )
        issue.add_reason(
            "A column with a single value has no variance, so it carries no "
            "information for statistics or modelling."
        )
        issues.append(issue)
    return issues


# ---------------------------------------------------------------------------
# 4. OUTLIERS (numeric continuous only)
# ---------------------------------------------------------------------------
def check_outliers(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag continuous columns with outliers using the IQR rule.

    The IQR (interquartile range) rule is a classic, distribution-free way to
    spot extreme values:
        Q1 = 25th percentile, Q3 = 75th percentile, IQR = Q3 - Q1
        anything below Q1 - 1.5*IQR or above Q3 + 1.5*IQR is an "outlier".

    Why it matters: outliers distort means, variances, correlations and many
    models. But they are not automatically errors -- a real billionaire in an
    income column is an outlier AND a true value. So we flag, never delete.
    """
    issues: list[HealthIssue] = []

    for col in profile.columns_of_type(SemanticType.NUMERIC_CONTINUOUS):
        series = df[col.name].dropna()
        if len(series) < 4:
            continue  # too few points for quartiles to mean anything

        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            continue  # no spread -> IQR rule is undefined/uninformative

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        mask = (series < lower) | (series > upper)
        n_out = int(mask.sum())
        if n_out == 0:
            continue

        pct = round(n_out / len(series) * 100, 2)
        severity = Severity.MEDIUM if pct >= 5 else Severity.LOW

        issue = HealthIssue(
            category=IssueCategory.OUTLIERS,
            severity=severity,
            column=col.name,
            title=f"'{col.name}' has {n_out} outlier(s) ({pct}% of values)",
            evidence={
                "n_outliers": n_out,
                "outlier_pct": pct,
                "lower_bound": round(lower, 4),
                "upper_bound": round(upper, 4),
                "min": float(series.min()),
                "max": float(series.max()),
            },
            recommendation=f"Inspect the extreme values in '{col.name}' before deciding.",
        )
        issue.add_reason(
            f"Using the IQR rule, values outside [{round(lower, 2)}, {round(upper, 2)}] "
            f"are unusually far from the middle 50% of the data."
        )
        issue.add_reason(
            "Outliers may be data-entry errors OR genuine rare events. We flag them "
            "so you can judge; we never remove them for you."
        )
        issues.append(issue)

    return issues


# ---------------------------------------------------------------------------
# 5. HIGH CARDINALITY (categorical with too many distinct values)
# ---------------------------------------------------------------------------
def check_high_cardinality(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag categorical columns that have a very large number of categories.

    Why it matters: a category with hundreds of levels explodes into hundreds
    of columns when one-hot encoded, hurts model performance, and often means
    the column is really closer to free text or an identifier.
    """
    issues: list[HealthIssue] = []
    for col in profile.columns_of_type(SemanticType.CATEGORICAL):
        # "high" relative to the dataset: many distinct values AND a large share
        # of them unique. 50 is a common practical threshold for one-hot pain.
        if col.n_unique >= 50:
            issue = HealthIssue(
                category=IssueCategory.CARDINALITY,
                severity=Severity.MEDIUM,
                column=col.name,
                title=f"'{col.name}' has high cardinality ({col.n_unique} categories)",
                evidence={"n_unique": col.n_unique, "unique_pct": col.unique_pct},
                recommendation=(
                    f"Group rare levels of '{col.name}' into 'Other', or use target/"
                    f"frequency encoding instead of one-hot."
                ),
            )
            issue.add_reason(
                "One-hot encoding this column would create one new column per "
                "category, bloating the feature space and inviting overfitting."
            )
            issues.append(issue)
    return issues


# ---------------------------------------------------------------------------
# 6. RARE CATEGORIES
# ---------------------------------------------------------------------------
def check_rare_categories(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag categorical columns that contain very rare levels.

    Why it matters: categories seen only once or twice give models almost
    nothing to learn from and can leak into test sets, giving false confidence.
    """
    issues: list[HealthIssue] = []
    for col in profile.columns_of_type(SemanticType.CATEGORICAL):
        series = df[col.name].dropna()
        if series.empty:
            continue
        counts = series.value_counts()
        rare = counts[counts <= 2]
        if len(rare) == 0:
            continue

        issue = HealthIssue(
            category=IssueCategory.RARE_CATEGORY,
            severity=Severity.LOW,
            column=col.name,
            title=f"'{col.name}' has {len(rare)} rare category value(s)",
            evidence={
                "n_rare_levels": int(len(rare)),
                "examples": {str(k): int(v) for k, v in rare.head(5).items()},
            },
            recommendation=f"Consider grouping rare levels of '{col.name}' into an 'Other' bucket.",
        )
        issue.add_reason(
            "Levels appearing only once or twice give a model too little signal to "
            "generalise, and can cause train/test mismatches."
        )
        issues.append(issue)
    return issues


# ---------------------------------------------------------------------------
# 7. CLASS IMBALANCE (binary columns -- likely targets)
# ---------------------------------------------------------------------------
def check_class_imbalance(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag binary columns whose two classes are very unequal.

    Why it matters: if 95% of rows are class A, a model can score 95% accuracy
    by always guessing A while being useless. Imbalance must be known up front
    so we pick the right metric (precision/recall/F1, not accuracy).
    """
    issues: list[HealthIssue] = []
    for col in profile.columns_of_type(SemanticType.BINARY):
        series = df[col.name].dropna()
        if series.empty:
            continue
        counts = series.value_counts(normalize=True)
        minority_pct = round(float(counts.min()) * 100, 2)

        if minority_pct < 10:
            severity = Severity.HIGH
        elif minority_pct < 25:
            severity = Severity.MEDIUM
        else:
            continue  # reasonably balanced, nothing to flag

        issue = HealthIssue(
            category=IssueCategory.IMBALANCE,
            severity=severity,
            column=col.name,
            title=f"'{col.name}' is imbalanced (minority class = {minority_pct}%)",
            evidence={
                "minority_pct": minority_pct,
                "distribution": {str(k): round(float(v) * 100, 2) for k, v in counts.items()},
            },
            recommendation=(
                f"If '{col.name}' is your target, use precision/recall/F1 (not accuracy) "
                f"and consider resampling or class weights."
            ),
        )
        issue.add_reason(
            f"With only {minority_pct}% in the minority class, a model can look "
            f"accurate while never actually learning the rare class."
        )
        issues.append(issue)
    return issues


# ---------------------------------------------------------------------------
# 8. INCONSISTENT VALUES (text/categorical formatting)
# ---------------------------------------------------------------------------
def check_inconsistent_values(df: pd.DataFrame, profile: DatasetProfile) -> list[HealthIssue]:
    """
    Flag categorical columns whose labels look like the same thing typed
    differently: "USA" vs "usa" vs " USA ".

    Why it matters: to a computer "USA" and "usa " are two different categories,
    silently splitting one real group into several and corrupting counts.
    """
    issues: list[HealthIssue] = []
    for col in profile.columns_of_type(SemanticType.CATEGORICAL):
        series = df[col.name].dropna().astype(str)
        if series.empty:
            continue

        raw_levels = set(series.unique())
        # Normalise: strip surrounding whitespace and lowercase.
        normalised = series.str.strip().str.lower()
        norm_levels = set(normalised.unique())

        # If normalising collapses levels together, we had inconsistent spellings.
        if len(norm_levels) < len(raw_levels):
            collapsed = len(raw_levels) - len(norm_levels)
            issue = HealthIssue(
                category=IssueCategory.INCONSISTENCY,
                severity=Severity.MEDIUM,
                column=col.name,
                title=f"'{col.name}' has inconsistent value formatting",
                evidence={
                    "raw_level_count": len(raw_levels),
                    "normalised_level_count": len(norm_levels),
                    "levels_merged_by_cleanup": collapsed,
                },
                recommendation=f"Standardise '{col.name}' (trim whitespace, unify casing).",
            )
            issue.add_reason(
                f"Cleaning whitespace and casing reduces {len(raw_levels)} distinct "
                f"labels to {len(norm_levels)}, meaning {collapsed} were the same value "
                f"written differently."
            )
            issue.add_reason(
                "Left unfixed, one real category is counted as several, distorting "
                "frequencies and any grouping."
            )
            issues.append(issue)
    return issues
