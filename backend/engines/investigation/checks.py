"""
The discovery detectors for the Investigation Engine (Engine 3).

Each function takes the raw DataFrame plus Engine 1's DatasetProfile (so it
knows what every column *means*) and returns a list of Finding objects.

Design rules that keep this honest and teachable:
  - We only ever look at columns whose semantic type makes sense for the test
    (e.g. we never correlate an IDENTIFIER, and we never average a CATEGORICAL).
  - Every finding records its evidence (the actual numbers) and its reasoning.
  - We compute *effect size / strength*, never a p-value. Significance is
    Engine 4's job, so every finding is flagged needs_significance_test=True.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.dataset_understanding.types import DatasetProfile, SemanticType
from .types import Finding, FindingType, Strength

# --- shared helpers -----------------------------------------------------------

# Semantic types we treat as "a real number we can do math on".
_NUMERIC_TYPES = {SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE}

# Semantic types we treat as "a grouping label".
_GROUP_TYPES = {SemanticType.CATEGORICAL, SemanticType.BINARY}


def _strength_from_score(score: float) -> Strength:
    """Map a 0..1 score to the coarse human label used in the UI."""
    if score >= 0.7:
        return Strength.VERY_STRONG
    if score >= 0.5:
        return Strength.STRONG
    if score >= 0.3:
        return Strength.MODERATE
    return Strength.WEAK


def _numeric_columns(profile: DatasetProfile) -> list[str]:
    return [c.name for c in profile.columns if c.semantic_type in _NUMERIC_TYPES]


def _group_columns(profile: DatasetProfile) -> list[str]:
    return [c.name for c in profile.columns if c.semantic_type in _GROUP_TYPES]


# --- 1. numeric <-> numeric correlations -------------------------------------

def find_correlations(
    df: pd.DataFrame,
    profile: DatasetProfile,
    min_abs_r: float = 0.3,
) -> list[Finding]:
    """
    Find pairs of numeric columns that move together.

    We compute TWO correlations for each pair and that difference is itself a
    lesson:
      - Pearson r  : measures a straight-line (linear) relationship.
      - Spearman r : measures any consistent up/down (monotonic) relationship,
                     even a curved one, because it works on ranks.

    If Pearson is weak but Spearman is strong, the relationship is real but
    *curved* -- a hint that a transformation (e.g. log) might help later.
    """
    numeric = _numeric_columns(profile)
    findings: list[Finding] = []
    if len(numeric) < 2:
        return findings

    sub = df[numeric]
    pearson = sub.corr(method="pearson")
    spearman = sub.corr(method="spearman")

    # Walk the upper triangle so each pair is considered once.
    for i in range(len(numeric)):
        for j in range(i + 1, len(numeric)):
            a, b = numeric[i], numeric[j]
            r = pearson.iloc[i, j]
            rho = spearman.iloc[i, j]
            if pd.isna(r) or pd.isna(rho):
                continue

            # Rank the pair by the stronger of the two coefficients.
            strongest = max(abs(float(r)), abs(float(rho)))
            if strongest < min_abs_r:
                continue

            direction = "positive" if (r if not pd.isna(r) else rho) >= 0 else "negative"
            nonlinear = abs(float(rho)) - abs(float(r)) >= 0.2

            finding = Finding(
                finding_type=FindingType.CORRELATION,
                title=f"{a} and {b} move {'together' if direction == 'positive' else 'in opposite directions'}",
                columns=[a, b],
                score=round(strongest, 4),
                strength=_strength_from_score(strongest),
                direction=direction,
                evidence={
                    "pearson_r": round(float(r), 4),
                    "spearman_r": round(float(rho), 4),
                    "nonlinear_hint": nonlinear,
                },
            )
            verb = "increases" if direction == "positive" else "decreases"
            finding.add_reason(
                f"As {a} goes up, {b} tends to {verb} (Pearson r = {float(r):.2f}, "
                f"Spearman r = {float(rho):.2f})."
            )
            if nonlinear:
                finding.add_reason(
                    "Spearman is notably stronger than Pearson, which suggests the "
                    "relationship is real but CURVED rather than a straight line. A "
                    "transformation (like log) may straighten it out in the Feature Lab."
                )
            finding.suggested_next_step = (
                "Confirm this with a correlation significance test in the Statistics "
                "step, then decide if both columns belong in the model (highly "
                "correlated features can be redundant)."
            )
            findings.append(finding)

    return findings


# --- 2. group differences (numeric across a category) ------------------------

def find_group_differences(
    df: pd.DataFrame,
    profile: DatasetProfile,
    min_score: float = 0.3,
) -> list[Finding]:
    """
    For each (grouping column, numeric column) pair, ask: does the numeric
    average change a lot from group to group?

    We measure this with a normalized "spread of group means":

        eta_like = std(group_means, weighted) / std(whole_column)

    Intuitively: how much of the column's overall variation is explained just by
    knowing which group a row is in. 0 = groups look identical; near 1 = the
    group almost entirely determines the value.
    """
    groups = _group_columns(profile)
    numerics = _numeric_columns(profile)
    findings: list[Finding] = []

    for g in groups:
        gcol = df[g]
        # Skip groupers with too many levels -- that is a data-quality issue,
        # not an interesting comparison, and Engine 2 already flags it.
        if gcol.nunique(dropna=True) > 20:
            continue

        for n in numerics:
            series = df[n]
            overall_std = float(series.std())
            if not np.isfinite(overall_std) or overall_std == 0:
                continue

            grouped = series.groupby(gcol, observed=True)
            means = grouped.mean()
            sizes = grouped.size()
            if means.count() < 2:
                continue

            # Weighted spread of the group means around the grand mean.
            grand_mean = float(series.mean())
            weighted_var = float(
                (sizes * (means - grand_mean) ** 2).sum() / sizes.sum()
            )
            eta_like = float(np.sqrt(weighted_var) / overall_std)
            score = min(1.0, round(eta_like, 4))
            if score < min_score:
                continue

            hi = means.idxmax()
            lo = means.idxmin()
            finding = Finding(
                finding_type=FindingType.GROUP_DIFFERENCE,
                title=f"{n} differs across {g}",
                columns=[n, g],
                score=score,
                strength=_strength_from_score(score),
                evidence={
                    "group_means": {
                        str(k): round(float(v), 4) for k, v in means.items()
                    },
                    "highest_group": str(hi),
                    "lowest_group": str(lo),
                    "spread_ratio": round(eta_like, 4),
                },
            )
            finding.add_reason(
                f"The average {n} is highest for {g} = '{hi}' "
                f"({means.max():.2f}) and lowest for '{lo}' ({means.min():.2f})."
            )
            finding.add_reason(
                f"Knowing the {g} group explains a meaningful share of the "
                f"variation in {n} (spread ratio {eta_like:.2f})."
            )
            finding.suggested_next_step = (
                f"Run a group-comparison test (t-test / ANOVA) in the Statistics "
                f"step to check the gap between {g} groups is not just chance."
            )
            findings.append(finding)

    return findings


# --- 3. relationship with the user's target ----------------------------------

def find_target_relationships(
    df: pd.DataFrame,
    profile: DatasetProfile,
    target: str,
    min_score: float = 0.25,
) -> list[Finding]:
    """
    If the user picked a target column (the thing they eventually want to
    predict), surface which features look most related to it. This is a preview
    of "what might be predictive" -- NOT a model, and NOT proof.

    Two cases:
      - Numeric target   : rank features by |correlation| with the target.
      - Category target  : for each numeric feature, measure how much its mean
                           differs across the target classes (same eta-like idea
                           as group differences).
    """
    tprofile = profile.column(target)
    if tprofile is None:
        return []

    findings: list[Finding] = []

    if tprofile.semantic_type in _NUMERIC_TYPES:
        numeric = [c for c in _numeric_columns(profile) if c != target]
        if not numeric:
            return []
        corr = df[numeric + [target]].corr(method="spearman")[target]
        for feat in numeric:
            rho = corr.get(feat)
            if rho is None or pd.isna(rho):
                continue
            score = abs(float(rho))
            if score < min_score:
                continue
            direction = "positive" if rho >= 0 else "negative"
            finding = Finding(
                finding_type=FindingType.TARGET_RELATIONSHIP,
                title=f"{feat} relates to target {target}",
                columns=[feat, target],
                score=round(score, 4),
                strength=_strength_from_score(score),
                direction=direction,
                evidence={"spearman_r": round(float(rho), 4)},
            )
            finding.add_reason(
                f"{feat} has a {direction} monotonic relationship with the target "
                f"{target} (Spearman r = {float(rho):.2f}), so it may carry "
                f"predictive signal."
            )
            finding.suggested_next_step = (
                "Keep this feature as a candidate predictor and confirm its "
                "relationship in the Statistics step."
            )
            findings.append(finding)

    elif tprofile.semantic_type in _GROUP_TYPES:
        numeric = _numeric_columns(profile)
        tcol = df[target]
        for feat in numeric:
            series = df[feat]
            overall_std = float(series.std())
            if not np.isfinite(overall_std) or overall_std == 0:
                continue
            grouped = series.groupby(tcol, observed=True)
            means = grouped.mean()
            sizes = grouped.size()
            if means.count() < 2:
                continue
            grand_mean = float(series.mean())
            weighted_var = float((sizes * (means - grand_mean) ** 2).sum() / sizes.sum())
            eta_like = float(np.sqrt(weighted_var) / overall_std)
            score = min(1.0, round(eta_like, 4))
            if score < min_score:
                continue
            hi, lo = means.idxmax(), means.idxmin()
            finding = Finding(
                finding_type=FindingType.TARGET_RELATIONSHIP,
                title=f"{feat} separates the {target} classes",
                columns=[feat, target],
                score=score,
                strength=_strength_from_score(score),
                evidence={
                    "class_means": {str(k): round(float(v), 4) for k, v in means.items()},
                    "highest_class": str(hi),
                    "lowest_class": str(lo),
                },
            )
            finding.add_reason(
                f"Average {feat} is quite different between target classes: "
                f"'{hi}' sits at {means.max():.2f} while '{lo}' sits at "
                f"{means.min():.2f}. Features that separate the classes are often "
                f"good predictors."
            )
            finding.suggested_next_step = (
                f"Treat {feat} as a promising predictor of {target}; confirm the "
                f"class gap in the Statistics step."
            )
            findings.append(finding)

    return findings


# --- 4. strongly skewed numeric distributions --------------------------------

def find_skewed_distributions(
    df: pd.DataFrame,
    profile: DatasetProfile,
    min_abs_skew: float = 1.0,
) -> list[Finding]:
    """
    Flag numeric columns with a long tail (|skew| >= 1). Skew matters because
    many models and statistics assume roughly symmetric data, and a few extreme
    values can dominate. The usual fix (a log/sqrt transform) lives in the
    Feature Lab -- here we just point it out.
    """
    findings: list[Finding] = []
    for col in profile.columns:
        if col.semantic_type not in _NUMERIC_TYPES:
            continue
        skew = col.stats.get("skew")
        if skew is None:
            continue
        if abs(float(skew)) < min_abs_skew:
            continue
        score = min(1.0, abs(float(skew)) / 3.0)
        tail = "right" if skew > 0 else "left"
        finding = Finding(
            finding_type=FindingType.DISTRIBUTION_SKEW,
            title=f"{col.name} is skewed to the {tail}",
            columns=[col.name],
            score=round(score, 4),
            strength=_strength_from_score(score),
            direction=tail,
            evidence={"skew": round(float(skew), 4)},
            needs_significance_test=False,  # skew is a fact, not a hypothesis
        )
        finding.add_reason(
            f"{col.name} has a skew of {float(skew):.2f}, meaning a long {tail} "
            f"tail of extreme values pulls the average away from the typical value."
        )
        finding.suggested_next_step = (
            "Consider a log or square-root transform in the Feature Lab to make "
            "this column more symmetric before modelling."
        )
        findings.append(finding)
    return findings


# --- 5. dominant category -----------------------------------------------------

def find_dominant_categories(
    df: pd.DataFrame,
    profile: DatasetProfile,
    dominance_pct: float = 90.0,
) -> list[Finding]:
    """
    Flag categorical/binary columns where a single level covers almost every
    row. Such columns carry little information and, if it is the target, signal
    class imbalance (which changes how we must score models later).
    """
    findings: list[Finding] = []
    for col in profile.columns:
        if col.semantic_type not in _GROUP_TYPES:
            continue
        series = df[col.name].dropna()
        if series.empty:
            continue
        counts = series.value_counts(normalize=True)
        top_level = counts.index[0]
        top_pct = float(counts.iloc[0]) * 100.0
        if top_pct < dominance_pct:
            continue
        score = min(1.0, (top_pct - 50.0) / 50.0)  # 50%->0, 100%->1
        finding = Finding(
            finding_type=FindingType.DOMINANT_CATEGORY,
            title=f"{col.name} is dominated by '{top_level}'",
            columns=[col.name],
            score=round(score, 4),
            strength=_strength_from_score(score),
            evidence={"top_level": str(top_level), "top_pct": round(top_pct, 2)},
            needs_significance_test=False,
        )
        finding.add_reason(
            f"'{top_level}' accounts for {top_pct:.1f}% of {col.name}, so the "
            f"column is almost constant and carries little distinguishing signal."
        )
        finding.suggested_next_step = (
            "If this is a feature, it may be safe to drop. If it is the target, "
            "treat this as class imbalance and use precision/recall/F1 instead of "
            "accuracy when scoring models."
        )
        findings.append(finding)
    return findings
