"""
Data Health Engine (Engine 2).

Public API:
    assess_health(df, profile=None) -> HealthReport

Answers "Can I trust this dataset?" by detecting missing values, duplicates,
outliers, constant/high-cardinality/inconsistent columns and class imbalance,
then reporting each as an evidence-backed, reasoned recommendation. It never
modifies the data.
"""

from .engine import assess_health
from .types import (
    HealthIssue,
    HealthReport,
    IssueCategory,
    Severity,
)

__all__ = [
    "assess_health",
    "HealthReport",
    "HealthIssue",
    "IssueCategory",
    "Severity",
]
