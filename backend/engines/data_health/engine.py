"""
Data Health Engine (Engine 2) -- orchestrator.

Public entry point of Engine 2. It answers:

    "Can I trust this dataset?"

Give it a DataFrame (and, optionally, Engine 1's DatasetProfile), and it runs
every health check, rolls the findings into a single explainable score, and
returns a HealthReport. It NEVER modifies the data -- it only reports.

Pipeline:
    1. Make sure we have a DatasetProfile (run Engine 1 if not supplied).
    2. Run all checks; collect every HealthIssue.
    3. Turn issues into a 0-100 score + A-F grade.
    4. Write plain-language summary headlines.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding.engine import understand_dataset
from engines.dataset_understanding.types import DatasetProfile

from . import checks
from .types import HealthReport, Severity


# The full battery of checks, in the order we want them reported.
_CHECKS = (
    checks.check_missing_values,
    checks.check_duplicate_rows,
    checks.check_constant_columns,
    checks.check_outliers,
    checks.check_high_cardinality,
    checks.check_rare_categories,
    checks.check_class_imbalance,
    checks.check_inconsistent_values,
)


def assess_health(
    df: pd.DataFrame,
    profile: DatasetProfile | None = None,
) -> HealthReport:
    """
    Assess the trustworthiness of a DataFrame.

    `profile` lets callers reuse an Engine 1 result they already computed; if
    omitted we compute it here so Engine 2 can be used standalone.
    """
    if profile is None:
        profile = understand_dataset(df)

    # --- Step 1 + 2: run every check and gather all issues -----------------
    issues = []
    for check in _CHECKS:
        issues.extend(check(df, profile))

    # Sort so the scariest problems surface first (critical -> info).
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    issues.sort(key=lambda i: severity_order[i.severity])

    # --- Step 3: score ------------------------------------------------------
    score, grade = _score(issues)

    report = HealthReport(
        score=score,
        grade=grade,
        n_rows=profile.n_rows,
        n_cols=profile.n_cols,
        issues=issues,
    )

    # --- Step 4: human summary ---------------------------------------------
    report.summary = _build_summary(report)

    return report


def _score(issues: list) -> tuple[float, str]:
    """
    Convert a list of issues into a 0-100 score and an A-F grade.

    The rule is deliberately simple and explainable (DetaBeta never hides its
    reasoning behind a black box): start at 100 and subtract each issue's
    severity weight. That's it. A perfectly clean dataset scores 100.
    """
    penalty = sum(i.severity.weight for i in issues)
    score = max(0.0, round(100.0 - penalty, 1))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return score, grade


def _build_summary(report: HealthReport) -> list[str]:
    """Write the 'at a glance' headlines a UI would show at the top of the report."""
    summary: list[str] = []

    summary.append(
        f"Health score: {report.score}/100 (grade {report.grade}) across "
        f"{report.n_rows} rows and {report.n_cols} columns."
    )

    if not report.issues:
        summary.append("No health issues detected -- this dataset looks clean and trustworthy.")
        return summary

    # Count issues by severity for a quick triage line.
    counts = {}
    for issue in report.issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1

    parts = [
        f"{counts[sev]} {sev.value}"
        for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO)
        if sev in counts
    ]
    summary.append(f"Found {len(report.issues)} issue(s): {', '.join(parts)}.")

    # Call out the single most urgent issue by name.
    top = report.issues[0]
    summary.append(
        f"Most urgent: {top.title} -- {top.recommendation}"
    )

    return summary
