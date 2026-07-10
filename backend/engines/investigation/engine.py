"""
Investigation Engine (Engine 3) orchestrator.

Public entry point:
    investigate(df, profile=None, target=None) -> InvestigationReport

It answers "What interesting things exist?" by running every discovery
detector, merging their findings, ranking them by strength, and writing a
plain-language summary for the Investigation screen.

It depends on Engine 1 (for semantic types). It is deliberately independent of
Engine 2: a dataset can be investigated even before it is cleaned, and Engine 3
never claims significance -- it produces *leads* that Engine 4 will confirm.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.dataset_understanding.types import DatasetProfile
from . import checks
from .types import FindingType, InvestigationReport


def investigate(
    df: pd.DataFrame,
    profile: DatasetProfile | None = None,
    target: str | None = None,
) -> InvestigationReport:
    """
    Run the full investigation.

    Args:
        df:      the raw dataset.
        profile: Engine 1's DatasetProfile. If omitted, we compute it so the
                 engine is convenient to call on its own.
        target:  optional column the user eventually wants to predict. When
                 given, we add a dedicated "relationship with target" analysis.

    Returns:
        An InvestigationReport with findings sorted strongest-first.
    """
    if profile is None:
        profile = understand_dataset(df)

    findings = []
    findings += checks.find_correlations(df, profile)
    findings += checks.find_group_differences(df, profile)
    findings += checks.find_skewed_distributions(df, profile)
    findings += checks.find_dominant_categories(df, profile)
    if target is not None:
        findings += checks.find_target_relationships(df, profile, target)

    # Rank strongest-first so the UI shows the most compelling leads on top.
    findings.sort(key=lambda f: f.score, reverse=True)

    report = InvestigationReport(
        n_findings=len(findings),
        findings=findings,
        target=target,
    )
    report.summary = _build_summary(report)
    return report


def _build_summary(report: InvestigationReport) -> list[str]:
    """Turn the raw findings into a few sentences a human reads first."""
    summary: list[str] = []

    if report.n_findings == 0:
        summary.append(
            "No strong patterns stood out. That is itself informative: the "
            "columns look fairly independent, so predicting anything here may be "
            "hard without more or better features."
        )
        return summary

    summary.append(
        f"Found {report.n_findings} lead(s) worth investigating, shown "
        f"strongest-first."
    )

    # Highlight the single strongest finding in words.
    top = report.findings[0]
    summary.append(f"Strongest lead: {top.title} (strength: {top.strength.value}).")

    # Count by type so the user sees the shape of what we found.
    by_type = {
        FindingType.CORRELATION: "correlation(s) between numeric columns",
        FindingType.GROUP_DIFFERENCE: "group difference(s)",
        FindingType.TARGET_RELATIONSHIP: "feature(s) related to your target",
        FindingType.DISTRIBUTION_SKEW: "skewed distribution(s)",
        FindingType.DOMINANT_CATEGORY: "dominant-category column(s)",
    }
    for ftype, label in by_type.items():
        n = len(report.of_type(ftype))
        if n:
            summary.append(f"- {n} {label}.")

    # The philosophy reminder: leads are not proof.
    if any(f.needs_significance_test for f in report.findings):
        summary.append(
            "Remember: these are patterns, not proof. The Statistics step "
            "(Engine 4) will test which of them are statistically significant."
        )
    return summary
