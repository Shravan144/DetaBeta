"""
Type definitions for the Data Health Engine (Engine 2).

Like Engine 1's types.py, this file is "just data" -- no logic. It defines the
vocabulary Engine 2 uses to describe the *trustworthiness* of a dataset.

Engine 2 answers one question:

    "Can I trust this dataset?"

It does NOT clean the data. That is the single most important idea here.
DetaBeta's philosophy is "recommend, don't force": we surface every problem,
explain why it matters, and suggest a fix -- but the human decides. So every
problem we find is captured as a `HealthIssue` that carries:

    - severity   : how much this should worry you
    - evidence   : the concrete numbers that prove the problem exists
    - recommendation : what we suggest doing about it
    - reasoning  : WHY we recommend that (never a bare instruction)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """
    How serious a health issue is.

    Ordered from harmless to dangerous. We attach a numeric weight to each so
    the engine can roll many issues up into a single 0-100 health score.
    """

    INFO = "info"          # worth knowing, not a problem
    LOW = "low"            # minor, safe to ignore for now
    MEDIUM = "medium"      # should be addressed before modelling
    HIGH = "high"          # likely to distort results if ignored
    CRITICAL = "critical"  # will almost certainly break analysis/modelling

    @property
    def weight(self) -> float:
        """Penalty applied to the health score when an issue of this severity exists."""
        return {
            Severity.INFO: 0.0,
            Severity.LOW: 2.0,
            Severity.MEDIUM: 6.0,
            Severity.HIGH: 12.0,
            Severity.CRITICAL: 25.0,
        }[self]


class IssueCategory(str, Enum):
    """The family a health issue belongs to. Used for grouping in the UI."""

    MISSING = "missing_values"
    DUPLICATES = "duplicate_rows"
    OUTLIERS = "outliers"
    CONSTANT = "constant_column"
    CARDINALITY = "high_cardinality"
    RARE_CATEGORY = "rare_category"
    IMBALANCE = "class_imbalance"
    INCONSISTENCY = "inconsistent_values"


@dataclass
class HealthIssue:
    """
    One concrete problem found in the data.

    This is the atom of Engine 2. Everything the UI shows in the "Health
    Report" is a list of these. Note how it mirrors Engine 1's philosophy:
    we never just flag something, we explain and recommend.
    """

    category: IssueCategory
    severity: Severity
    title: str                    # short human summary, e.g. "'age' has 20% missing values"
    column: str | None = None     # which column (None = whole-dataset issue)
    evidence: dict[str, Any] = field(default_factory=dict)  # the proving numbers
    recommendation: str = ""      # what we suggest doing
    reasoning: list[str] = field(default_factory=list)      # WHY we suggest it

    def add_reason(self, reason: str) -> None:
        self.reasoning.append(reason)


@dataclass
class HealthReport:
    """
    Everything Engine 2 learned about the dataset's trustworthiness.

    `score` is a 0-100 summary (100 = pristine). It is deliberately a rough,
    explainable heuristic -- not a magic number. `issues` is the real content:
    the full, evidence-backed list a human should read.
    """

    score: float                             # 0-100, higher is healthier
    grade: str                               # A/B/C/D/F, a friendly label for the score
    n_rows: int = 0
    n_cols: int = 0
    issues: list[HealthIssue] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)  # plain-language headlines

    def issues_by_severity(self, severity: Severity) -> list[HealthIssue]:
        return [i for i in self.issues if i.severity == severity]

    def issues_for_column(self, column: str) -> list[HealthIssue]:
        return [i for i in self.issues if i.column == column]

    def issues_in_category(self, category: IssueCategory) -> list[HealthIssue]:
        return [i for i in self.issues if i.category == category]
