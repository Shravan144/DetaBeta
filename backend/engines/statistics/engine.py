"""
Engine 4: Statistics -- "Are these findings statistically meaningful?"

This orchestrator does three things:

  1. Turns Engine 3's LEADS into concrete significance tests. Each Finding type
     maps to the right test:
         CORRELATION / TARGET_RELATIONSHIP (numeric~numeric) -> correlation_test
         GROUP_DIFFERENCE / TARGET_RELATIONSHIP (num~cat)     -> group_difference_test
     (skew and dominant-category findings are facts, not hypotheses, so we skip
      them -- Engine 3 already marked them needs_significance_test=False.)

  2. Adds a few TARGET-focused tests the user cares about most, including a
     chi-square when both the target and a feature are categorical.

  3. Corrects for MULTIPLE COMPARISONS. Running many tests at alpha=0.05 means
     roughly 1 in 20 "significant" results is a fluke. The Bonferroni rule
     tightens the threshold to alpha / (number of tests) so we do not fool
     ourselves. We report BOTH the raw and corrected verdicts.

We deliberately reuse Engine 1's semantic types and Engine 3's findings instead
of re-deriving them -- that is the whole point of building the engines in order.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.dataset_understanding.types import DatasetProfile, SemanticType
from engines.investigation import investigate
from engines.investigation.types import FindingType, InvestigationReport

from .tests import chi_square_test, correlation_test, group_difference_test
from .types import Significance, StatisticsReport, StatTest, TestKind

# Semantic types we treat as "numeric" and "categorical" for test selection.
_NUMERIC = {SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE}
_CATEGORICAL = {SemanticType.CATEGORICAL, SemanticType.BINARY}


def _semantic_map(profile: DatasetProfile) -> dict[str, SemanticType]:
    return {c.name: c.semantic_type for c in profile.columns}


def _test_from_finding(df, finding, semantics, alpha) -> StatTest | None:
    """Pick and run the correct test for one Engine 3 finding."""
    if not finding.needs_significance_test:
        return None

    if finding.finding_type == FindingType.CORRELATION:
        a, b = finding.columns[0], finding.columns[1]
        return correlation_test(df, a, b, alpha)

    if finding.finding_type in (
        FindingType.GROUP_DIFFERENCE,
        FindingType.TARGET_RELATIONSHIP,
    ):
        # figure out which column is numeric and which is the grouping category
        c0, c1 = finding.columns[0], finding.columns[1]
        t0, t1 = semantics.get(c0), semantics.get(c1)
        if t0 in _NUMERIC and t1 in _NUMERIC:
            return correlation_test(df, c0, c1, alpha)
        if t0 in _NUMERIC and t1 in _CATEGORICAL:
            return group_difference_test(df, c0, c1, alpha)
        if t1 in _NUMERIC and t0 in _CATEGORICAL:
            return group_difference_test(df, c1, c0, alpha)
        if t0 in _CATEGORICAL and t1 in _CATEGORICAL:
            return chi_square_test(df, c0, c1, alpha)
    return None


def _dedupe_key(t: StatTest) -> tuple:
    """Two tests are 'the same' if same kind on the same (unordered) columns."""
    return (t.test_kind, frozenset(t.columns))


def analyze_significance(
    df: pd.DataFrame,
    profile: DatasetProfile | None = None,
    investigation: InvestigationReport | None = None,
    target: str | None = None,
    alpha: float = 0.05,
) -> StatisticsReport:
    """
    Run Engine 4 over a dataset.

    You can pass in the Engine 1 profile and Engine 3 report if you already have
    them (efficient); otherwise we compute them so Engine 4 can be run on its own.
    """
    if profile is None:
        profile = understand_dataset(df)
    if investigation is None:
        investigation = investigate(df, profile=profile, target=target)
    if target is None:
        target = investigation.target

    semantics = _semantic_map(profile)

    tests: list[StatTest] = []
    seen: set[tuple] = set()

    # 1) Confirm every testable Engine 3 lead.
    for finding in investigation.findings:
        t = _test_from_finding(df, finding, semantics, alpha)
        if t is None:
            continue
        key = _dedupe_key(t)
        if key in seen:
            continue
        seen.add(key)
        tests.append(t)

    # 2) Extra target-vs-categorical chi-square tests, which Engine 3 does not
    #    surface directly but are exactly what a modeller wants to know.
    if target and semantics.get(target) in _CATEGORICAL:
        for col, sem in semantics.items():
            if col == target or sem not in _CATEGORICAL:
                continue
            t = chi_square_test(df, col, target, alpha)
            key = _dedupe_key(t)
            if key not in seen:
                seen.add(key)
                tests.append(t)

    # 3) Multiple-comparison correction.
    n_tests = len(tests)
    bonferroni_alpha = alpha / n_tests if n_tests > 0 else None

    report = StatisticsReport(
        n_tests=n_tests,
        tests=tests,
        alpha=alpha,
        bonferroni_alpha=bonferroni_alpha,
        target=target,
    )
    _summarize(report)
    return report


def _summarize(report: StatisticsReport) -> None:
    """Write the plain-language roll-up shown on the Evidence screen."""
    n = report.n_tests
    if n == 0:
        report.summary.append(
            "No hypotheses were available to test. Engine 3 may only have found "
            "descriptive facts (like skew), which do not require a significance test."
        )
        return

    sig = report.significant()
    n_sig = len(sig)
    report.summary.append(
        f"Ran {n} statistical test{'s' if n != 1 else ''} at a "
        f"{report.alpha:.0%} significance level."
    )
    report.summary.append(
        f"{n_sig} of {n} came back statistically significant -- unlikely to be "
        f"explained by random chance alone."
    )

    # Highlight the strongest confirmed effect (by effect size, not p-value).
    with_effect = [t for t in sig if t.effect_value is not None]
    if with_effect:
        strongest = max(with_effect, key=lambda t: abs(t.effect_value))
        report.summary.append(
            f"Strongest confirmed effect: {strongest.title} "
            f"({strongest.effect_metric} = {strongest.effect_value}, "
            f"{strongest.effect_size.value} effect)."
        )

    # The multiple-comparison honesty note.
    if report.bonferroni_alpha is not None and n > 1:
        survivors = [t for t in sig if t.p_value < report.bonferroni_alpha]
        report.summary.append(
            f"Because we ran {n} tests, a stricter Bonferroni threshold of "
            f"{report.bonferroni_alpha:.4f} guards against false positives; "
            f"{len(survivors)} result{'s' if len(survivors) != 1 else ''} "
            f"survive{'s' if len(survivors) == 1 else ''} that stricter bar."
        )

    report.summary.append(
        "Remember: 'significant' means 'probably not luck', NOT 'large' or "
        "'important'. Always read the effect size alongside the p-value."
    )
