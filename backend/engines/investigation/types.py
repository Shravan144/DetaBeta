"""
Type definitions for the Investigation Engine (Engine 3).

Like Engine 1 and 2, this module is "just data" -- no logic. It defines the
vocabulary the engine uses to describe *discoveries*.

What is a "discovery" here?
---------------------------
Engine 3 hunts for interesting structure in the data: columns that move
together, groups that behave differently, features that seem to relate to a
target, lopsided distributions, and so on.

BIG IDEA (and a core data-science lesson):
    Finding a pattern is NOT the same as proving it is real.

A correlation of 0.6 in 20 rows might be pure luck. A gap between two group
means might vanish once you account for sample size. So Engine 3 is honest: it
reports the *strength* and *direction* of what it sees, explains why it is
worth a look, and then explicitly hands the question of "is this statistically
significant?" to Engine 4 (Statistics). Every finding therefore carries a
`needs_significance_test` caveat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FindingType(str, Enum):
    """The kind of interesting structure a finding describes."""

    # Two numeric columns move together (Pearson / Spearman).
    CORRELATION = "correlation"

    # A numeric column's average differs across the levels of a category.
    GROUP_DIFFERENCE = "group_difference"

    # A feature looks related to the user-chosen target column.
    TARGET_RELATIONSHIP = "target_relationship"

    # A numeric column is strongly skewed (long tail) -> may need transforming.
    DISTRIBUTION_SKEW = "distribution_skew"

    # One category level dominates almost all rows.
    DOMINANT_CATEGORY = "dominant_category"


class Strength(str, Enum):
    """
    A human label for how strong a finding is.

    We keep a numeric 0..1 score too (see Finding.score), but this coarse label
    is what the UI shows first because "strong" is easier to grasp than "0.72".
    """

    WEAK = "weak"          # score < 0.3  -> probably noise, shown low or hidden
    MODERATE = "moderate"  # 0.3 <= score < 0.5
    STRONG = "strong"      # 0.5 <= score < 0.7
    VERY_STRONG = "very_strong"  # score >= 0.7


@dataclass
class Finding:
    """
    ONE interesting thing Engine 3 noticed.

    The `reasoning` list and `needs_significance_test` flag are the heart of
    DetaBeta's philosophy: we explain *why* this is worth attention and we are
    upfront that a pattern is only a lead until Engine 4 confirms it.
    """

    finding_type: FindingType
    title: str                       # one-line headline, e.g. "fare rises with class"
    columns: list[str]               # the column(s) involved

    score: float                     # normalized 0..1 importance for ranking
    strength: Strength               # the human label derived from score
    direction: str | None = None     # "positive" / "negative" / None

    # The numbers that back the claim (r value, group means, effect size...).
    evidence: dict[str, Any] = field(default_factory=dict)

    # Step-by-step "why we surfaced this".
    reasoning: list[str] = field(default_factory=list)

    # What the user could do next with this lead.
    suggested_next_step: str = ""

    # Almost always True in Engine 3: a lead still needs Engine 4 to confirm it.
    needs_significance_test: bool = True

    def add_reason(self, reason: str) -> None:
        self.reasoning.append(reason)


@dataclass
class InvestigationReport:
    """Everything Engine 3 discovered about a dataset."""

    n_findings: int
    findings: list[Finding] = field(default_factory=list)

    # The target column the user asked us to focus on, if any.
    target: str | None = None

    # Plain-language roll-up shown at the top of the Investigation screen.
    summary: list[str] = field(default_factory=list)

    def top(self, k: int = 5) -> list[Finding]:
        """Return the k strongest findings (already sorted by the engine)."""
        return self.findings[:k]

    def of_type(self, finding_type: FindingType) -> list[Finding]:
        return [f for f in self.findings if f.finding_type == finding_type]
