"""
Type definitions for the Statistics Engine (Engine 4).

Engine 3 (Investigation) found *leads*: "fare seems to drop as class number
rises", "survival rate looks different between sexes", and so on. It was always
honest that a lead is not proof. Engine 4 is where we do the proving.

WHAT "PROVING" MEANS HERE (the core lesson of this engine)
----------------------------------------------------------
A statistical test asks a very specific question:

    "If there were REALLY no effect in the world, how surprising would it be to
     see a pattern at least this strong, just from random sampling?"

That surprise is the **p-value**. Small p (say < 0.05) => the pattern is hard to
explain by luck alone => we call it "statistically significant".

But a p-value alone is dangerously incomplete, so every result here also carries:

  * an EFFECT SIZE  -> "how big is the effect?" (a tiny effect can be
    'significant' in a huge dataset yet be practically meaningless).
  * a plain-language INTERPRETATION and honest CAVEATS.

This module is "just data" -- the vocabulary Engine 4 speaks. The logic lives
in tests.py and engine.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TestKind(str, Enum):
    """Which statistical test we ran."""

    # Is the linear correlation between two numeric columns real?
    PEARSON_CORRELATION = "pearson_correlation"

    # Is the monotonic (rank) correlation real? (robust to curves/outliers)
    SPEARMAN_CORRELATION = "spearman_correlation"

    # Do TWO groups have different means? (Welch's t-test)
    T_TEST = "t_test"

    # Do THREE OR MORE groups have different means? (one-way ANOVA)
    ANOVA = "anova"

    # Are two categorical variables associated? (chi-square of independence)
    CHI_SQUARE = "chi_square"


class Significance(str, Enum):
    """A human label derived from the p-value and our alpha threshold."""

    SIGNIFICANT = "significant"          # p < alpha  -> unlikely to be luck
    NOT_SIGNIFICANT = "not_significant"  # p >= alpha -> could easily be luck
    INCONCLUSIVE = "inconclusive"        # test could not run reliably (too little data)


class EffectSize(str, Enum):
    """
    A human label for how BIG the effect is, independent of the p-value.

    Thresholds follow Cohen's widely used conventions. The exact metric depends
    on the test (r, Cohen's d, eta-squared, Cramer's V), but we always map it to
    one of these buckets so a beginner can reason about magnitude.
    """

    NEGLIGIBLE = "negligible"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass
class StatTest:
    """
    The result of ONE statistical test.

    This is the heart of Engine 4. Notice how p-value, effect size, and a
    written interpretation always travel together -- you are never shown a
    naked p-value.
    """

    test_kind: TestKind
    title: str                       # e.g. "survived differs by sex"
    columns: list[str]               # the column(s) tested

    # --- The core numbers ---
    statistic: float                 # the test statistic (t, F, chi2, or r)
    p_value: float                   # probability of seeing this by luck if no effect
    significance: Significance       # label derived from p_value vs alpha
    alpha: float = 0.05              # the significance threshold we used

    # --- Effect size (magnitude, not luck) ---
    effect_metric: str = ""          # which metric: "cohens_d", "eta_squared", ...
    effect_value: float | None = None
    effect_size: EffectSize | None = None

    # Degrees of freedom / sample sizes, useful context for the reader.
    details: dict[str, Any] = field(default_factory=dict)

    # Plain-language "what this means" + honest warnings.
    interpretation: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def add_interpretation(self, line: str) -> None:
        self.interpretation.append(line)

    def add_caveat(self, line: str) -> None:
        self.caveats.append(line)


@dataclass
class StatisticsReport:
    """Everything Engine 4 tested on a dataset."""

    n_tests: int
    tests: list[StatTest] = field(default_factory=list)

    # The significance threshold used across the run.
    alpha: float = 0.05

    # If we corrected for running many tests at once, the adjusted threshold.
    # (Running 20 tests at alpha=0.05 means ~1 false "significant" by chance.)
    bonferroni_alpha: float | None = None

    target: str | None = None

    # Plain-language roll-up shown at the top of the Evidence screen.
    summary: list[str] = field(default_factory=list)

    def significant(self) -> list[StatTest]:
        """Return only the tests that came back significant."""
        return [t for t in self.tests if t.significance == Significance.SIGNIFICANT]

    def of_kind(self, kind: TestKind) -> list[StatTest]:
        return [t for t in self.tests if t.test_kind == kind]
