"""
The statistical tests for Engine 4, one function per test.

Every function follows the same honest recipe:
  1. Guard: do we have enough clean data to run this reliably? If not, return
     an INCONCLUSIVE result instead of a misleading number.
  2. Run the test with scipy -> get a statistic and a p-value.
  3. Compute an EFFECT SIZE (magnitude), because a p-value alone lies about
     importance.
  4. Write plain-language interpretation + caveats.

We lean on scipy.stats, the standard, well-tested scientific library, rather
than re-deriving formulas by hand.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .types import EffectSize, Significance, StatTest, TestKind

# Minimum sample sizes below which a test is not trustworthy. These are
# pragmatic teaching thresholds, not hard mathematical laws.
MIN_CORRELATION_N = 8
MIN_GROUP_N = 5          # per group
MIN_CHI_EXPECTED = 5     # smallest expected cell count for a valid chi-square


# --------------------------------------------------------------------------- #
# Effect-size label helpers (Cohen's conventions)
# --------------------------------------------------------------------------- #
def _label_r(r: float) -> EffectSize:
    """Correlation r as an effect size."""
    a = abs(r)
    if a < 0.1:
        return EffectSize.NEGLIGIBLE
    if a < 0.3:
        return EffectSize.SMALL
    if a < 0.5:
        return EffectSize.MEDIUM
    return EffectSize.LARGE


def _label_cohens_d(d: float) -> EffectSize:
    a = abs(d)
    if a < 0.2:
        return EffectSize.NEGLIGIBLE
    if a < 0.5:
        return EffectSize.SMALL
    if a < 0.8:
        return EffectSize.MEDIUM
    return EffectSize.LARGE


def _label_eta_squared(eta2: float) -> EffectSize:
    if eta2 < 0.01:
        return EffectSize.NEGLIGIBLE
    if eta2 < 0.06:
        return EffectSize.SMALL
    if eta2 < 0.14:
        return EffectSize.MEDIUM
    return EffectSize.LARGE


def _label_cramers_v(v: float) -> EffectSize:
    if v < 0.1:
        return EffectSize.NEGLIGIBLE
    if v < 0.3:
        return EffectSize.SMALL
    if v < 0.5:
        return EffectSize.MEDIUM
    return EffectSize.LARGE


def _significance(p: float, alpha: float) -> Significance:
    return Significance.SIGNIFICANT if p < alpha else Significance.NOT_SIGNIFICANT


def _p_phrase(p: float) -> str:
    """Human phrasing for a p-value."""
    if p < 0.001:
        return "far below 0.001"
    if p < 0.01:
        return f"{p:.4f} (below 0.01)"
    if p < 0.05:
        return f"{p:.4f} (below 0.05)"
    return f"{p:.4f}"


# --------------------------------------------------------------------------- #
# 1 & 2. Correlation tests (Pearson + Spearman)
# --------------------------------------------------------------------------- #
def correlation_test(
    df: pd.DataFrame, col_a: str, col_b: str, alpha: float = 0.05
) -> StatTest:
    """
    Test whether two numeric columns are genuinely correlated.

    We run Pearson (straight-line strength) as the headline test but also report
    Spearman (rank/monotonic) in the details, because a big gap between them is
    the classic sign of a curved relationship.
    """
    pair = df[[col_a, col_b]].dropna()
    n = len(pair)

    if n < MIN_CORRELATION_N:
        return StatTest(
            test_kind=TestKind.PEARSON_CORRELATION,
            title=f"correlation between {col_a} and {col_b}",
            columns=[col_a, col_b],
            statistic=float("nan"),
            p_value=float("nan"),
            significance=Significance.INCONCLUSIVE,
            alpha=alpha,
            details={"n": n},
            interpretation=[
                f"Only {n} rows have both {col_a} and {col_b} present -- too few "
                f"to test a correlation reliably (need at least {MIN_CORRELATION_N})."
            ],
            caveats=["Collect more data before trusting any correlation here."],
        )

    r, p = stats.pearsonr(pair[col_a], pair[col_b])
    rho, _ = stats.spearmanr(pair[col_a], pair[col_b])

    result = StatTest(
        test_kind=TestKind.PEARSON_CORRELATION,
        title=f"correlation between {col_a} and {col_b}",
        columns=[col_a, col_b],
        statistic=round(float(r), 4),
        p_value=float(p),
        significance=_significance(p, alpha),
        alpha=alpha,
        effect_metric="pearson_r",
        effect_value=round(float(r), 4),
        effect_size=_label_r(r),
        details={"n": n, "spearman_r": round(float(rho), 4)},
    )

    direction = "positive" if r > 0 else "negative"
    if result.significance == Significance.SIGNIFICANT:
        result.add_interpretation(
            f"There is a statistically significant {direction} linear "
            f"correlation (r = {r:.2f}, p = {_p_phrase(p)}). A {direction} "
            f"correlation means that as {col_a} goes up, {col_b} tends to go "
            f"{'up' if r > 0 else 'down'}."
        )
        result.add_interpretation(
            f"The effect size is {result.effect_size.value}: r = {r:.2f} means "
            f"about {r**2 * 100:.0f}% of the variation in one column moves "
            f"together with the other."
        )
    else:
        result.add_interpretation(
            f"The correlation (r = {r:.2f}) is NOT statistically significant "
            f"(p = {_p_phrase(p)}). With {n} rows, a relationship this weak could "
            f"easily appear by chance."
        )

    if abs(rho) - abs(r) > 0.15:
        result.add_caveat(
            f"Spearman (r = {rho:.2f}) is noticeably stronger than Pearson "
            f"(r = {r:.2f}): the real relationship is likely CURVED, not a "
            f"straight line. Consider a transform in the Feature Lab."
        )
    result.add_caveat(
        "Correlation is not causation -- this test says the two move together, "
        "not that one causes the other."
    )
    return result


# --------------------------------------------------------------------------- #
# 3 & 4. Group mean differences (t-test for 2 groups, ANOVA for 3+)
# --------------------------------------------------------------------------- #
def group_difference_test(
    df: pd.DataFrame, numeric_col: str, group_col: str, alpha: float = 0.05
) -> StatTest:
    """
    Test whether the mean of `numeric_col` differs across the levels of
    `group_col`. Picks a t-test (exactly 2 groups) or ANOVA (3+ groups).
    """
    pair = df[[numeric_col, group_col]].dropna()
    # Keep only groups that have enough rows to contribute reliably.
    counts = pair[group_col].value_counts()
    valid_levels = counts[counts >= MIN_GROUP_N].index.tolist()
    samples = [
        pair.loc[pair[group_col] == lvl, numeric_col].to_numpy()
        for lvl in valid_levels
    ]
    k = len(samples)

    if k < 2:
        return StatTest(
            test_kind=TestKind.T_TEST,
            title=f"{numeric_col} by {group_col}",
            columns=[numeric_col, group_col],
            statistic=float("nan"),
            p_value=float("nan"),
            significance=Significance.INCONCLUSIVE,
            alpha=alpha,
            details={"valid_groups": k},
            interpretation=[
                f"Fewer than two groups of {group_col} have at least "
                f"{MIN_GROUP_N} rows, so a group comparison is not reliable."
            ],
            caveats=["Collect more data per group before comparing them."],
        )

    if k == 2:
        # Welch's t-test: does NOT assume the two groups have equal variance,
        # which is the safer default in the real world.
        t, p = stats.ttest_ind(samples[0], samples[1], equal_var=False)
        # Cohen's d with a pooled standard deviation = standardized gap between means.
        m0, m1 = np.mean(samples[0]), np.mean(samples[1])
        s0, s1 = np.std(samples[0], ddof=1), np.std(samples[1], ddof=1)
        n0, n1 = len(samples[0]), len(samples[1])
        pooled = np.sqrt(((n0 - 1) * s0**2 + (n1 - 1) * s1**2) / (n0 + n1 - 2))
        d = (m1 - m0) / pooled if pooled > 0 else 0.0

        result = StatTest(
            test_kind=TestKind.T_TEST,
            title=f"{numeric_col} differs by {group_col}",
            columns=[numeric_col, group_col],
            statistic=round(float(t), 4),
            p_value=float(p),
            significance=_significance(p, alpha),
            alpha=alpha,
            effect_metric="cohens_d",
            effect_value=round(float(d), 4),
            effect_size=_label_cohens_d(d),
            details={
                "groups": [str(x) for x in valid_levels],
                "means": {
                    str(valid_levels[0]): round(float(m0), 4),
                    str(valid_levels[1]): round(float(m1), 4),
                },
                "n_per_group": {
                    str(valid_levels[0]): int(n0),
                    str(valid_levels[1]): int(n1),
                },
            },
        )
        if result.significance == Significance.SIGNIFICANT:
            result.add_interpretation(
                f"The mean {numeric_col} is significantly different between "
                f"'{valid_levels[0]}' ({m0:.2f}) and '{valid_levels[1]}' "
                f"({m1:.2f}) -- p = {_p_phrase(p)}."
            )
            result.add_interpretation(
                f"The effect size is {result.effect_size.value} (Cohen's d = "
                f"{d:.2f}): the gap is about {abs(d):.1f} standard deviations wide."
            )
        else:
            result.add_interpretation(
                f"The means ({m0:.2f} vs {m1:.2f}) are NOT significantly "
                f"different (p = {_p_phrase(p)}). The observed gap is within what "
                f"random sampling could produce."
            )
        return result

    # 3+ groups -> one-way ANOVA.
    f_stat, p = stats.f_oneway(*samples)
    # eta-squared = between-group variance / total variance (share explained).
    grand = np.concatenate(samples)
    grand_mean = grand.mean()
    ss_between = sum(len(s) * (s.mean() - grand_mean) ** 2 for s in samples)
    ss_total = ((grand - grand_mean) ** 2).sum()
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0

    result = StatTest(
        test_kind=TestKind.ANOVA,
        title=f"{numeric_col} differs across {group_col}",
        columns=[numeric_col, group_col],
        statistic=round(float(f_stat), 4),
        p_value=float(p),
        significance=_significance(p, alpha),
        alpha=alpha,
        effect_metric="eta_squared",
        effect_value=round(float(eta2), 4),
        effect_size=_label_eta_squared(eta2),
        details={
            "groups": [str(x) for x in valid_levels],
            "means": {
                str(lvl): round(float(np.mean(s)), 4)
                for lvl, s in zip(valid_levels, samples)
            },
        },
    )
    if result.significance == Significance.SIGNIFICANT:
        result.add_interpretation(
            f"At least one group of {group_col} has a significantly different "
            f"mean {numeric_col} (ANOVA F = {f_stat:.2f}, p = {_p_phrase(p)})."
        )
        result.add_interpretation(
            f"The effect size is {result.effect_size.value}: {group_col} explains "
            f"about {eta2 * 100:.0f}% of the variation in {numeric_col}."
        )
    else:
        result.add_interpretation(
            f"No group of {group_col} stands out with a different mean "
            f"{numeric_col} (p = {_p_phrase(p)})."
        )
    result.add_caveat(
        "ANOVA tells you that SOME group differs, not WHICH ones. A follow-up "
        "pairwise test would be needed to pinpoint the pair(s)."
    )
    return result


# --------------------------------------------------------------------------- #
# 5. Chi-square test of independence (categorical vs categorical)
# --------------------------------------------------------------------------- #
def chi_square_test(
    df: pd.DataFrame, col_a: str, col_b: str, alpha: float = 0.05
) -> StatTest:
    """
    Test whether two categorical columns are associated (not independent).

    Example: is `survived` (yes/no) associated with `sex` (male/female)?
    """
    pair = df[[col_a, col_b]].dropna()
    table = pd.crosstab(pair[col_a], pair[col_b])

    if table.shape[0] < 2 or table.shape[1] < 2:
        return StatTest(
            test_kind=TestKind.CHI_SQUARE,
            title=f"association between {col_a} and {col_b}",
            columns=[col_a, col_b],
            statistic=float("nan"),
            p_value=float("nan"),
            significance=Significance.INCONCLUSIVE,
            alpha=alpha,
            interpretation=[
                f"One of {col_a}/{col_b} has fewer than two categories present, "
                f"so there is nothing to compare."
            ],
        )

    chi2, p, dof, expected = stats.chi2_contingency(table)
    n = int(table.to_numpy().sum())
    # Cramer's V = association strength scaled to 0..1.
    min_dim = min(table.shape[0] - 1, table.shape[1] - 1)
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if n > 0 and min_dim > 0 else 0.0

    result = StatTest(
        test_kind=TestKind.CHI_SQUARE,
        title=f"{col_a} is associated with {col_b}",
        columns=[col_a, col_b],
        statistic=round(float(chi2), 4),
        p_value=float(p),
        significance=_significance(p, alpha),
        alpha=alpha,
        effect_metric="cramers_v",
        effect_value=round(float(cramers_v), 4),
        effect_size=_label_cramers_v(cramers_v),
        details={"dof": int(dof), "n": n},
    )

    if expected.min() < MIN_CHI_EXPECTED:
        result.add_caveat(
            f"Some category combinations were expected to appear fewer than "
            f"{MIN_CHI_EXPECTED} times (smallest expected = {expected.min():.1f}). "
            f"The chi-square approximation is shaky here; treat the p-value with care."
        )

    if result.significance == Significance.SIGNIFICANT:
        result.add_interpretation(
            f"{col_a} and {col_b} are significantly associated "
            f"(chi-square = {chi2:.2f}, p = {_p_phrase(p)}): knowing one tells "
            f"you something about the other."
        )
        result.add_interpretation(
            f"The association strength is {result.effect_size.value} "
            f"(Cramer's V = {cramers_v:.2f})."
        )
    else:
        result.add_interpretation(
            f"{col_a} and {col_b} show no significant association "
            f"(p = {_p_phrase(p)}): they look independent."
        )
    return result
