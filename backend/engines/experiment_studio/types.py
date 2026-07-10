"""
Type definitions for the Experiment Studio Engine (Engine 7).

Answers: "Which model performs best?"

This is the first engine that ACTUALLY TRAINS models. It takes the plan
produced by Engine 6 (problem type, features, algorithms, validation strategy)
and runs it honestly:

  - build a leak-free preprocessing pipeline (impute + scale + encode)
  - train each recommended algorithm inside cross-validation
  - score every model on the SAME folds so the comparison is fair
  - report results with plain-language interpretation and a recommended winner

Everything carries reasoning, matching DetaBeta's philosophy: never present a
number without explaining what it means and how much to trust it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricScore:
    """
    One metric's cross-validated result for one model.

    `mean` is the average across folds; `std` is how much it wobbled between
    folds. A large std relative to the mean means the score is unstable and
    should be trusted less -- an important honesty signal.
    """

    name: str                       # e.g. "accuracy", "f1", "rmse"
    mean: float
    std: float
    # Higher-is-better for most classification metrics; for error metrics
    # (rmse, mae) lower is better. We store this so the UI can render arrows
    # and the engine can rank correctly.
    higher_is_better: bool = True

    def display(self) -> str:
        """A compact 'mean ± std' string for logs and the UI."""
        return f"{self.mean:.4f} ± {self.std:.4f}"


@dataclass
class ModelResult:
    """The outcome of training and evaluating ONE algorithm."""

    name: str                                   # "Logistic Regression"
    rank_requested: int                         # the rank Engine 6 gave it
    is_baseline: bool = False
    # The primary metric's mean, copied out for easy sorting/among models.
    primary_metric: str = ""
    primary_score: float = 0.0
    primary_higher_is_better: bool = True
    # All metrics we computed (primary + cross-checks).
    metrics: dict[str, MetricScore] = field(default_factory=dict)
    # How long training + CV took, in seconds (a real cost signal).
    train_seconds: float = 0.0
    # If training failed, we keep going with the others and record why.
    failed: bool = False
    error: str = ""
    reasoning: list[str] = field(default_factory=list)


@dataclass
class ExperimentReport:
    """The full results of the modelling experiment."""

    target: str
    problem_type: str
    primary_metric: str = ""
    n_rows_used: int = 0
    n_features_used: int = 0

    # Every model we tried, in the order Engine 6 requested them.
    results: list[ModelResult] = field(default_factory=list)

    # The name of the model we recommend, and why it won.
    best_model: str = ""
    best_reasoning: list[str] = field(default_factory=list)

    # Did a complex model actually beat the simple baseline? (a key lesson)
    beat_baseline: bool = False
    baseline_comparison: str = ""

    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    def best(self) -> ModelResult | None:
        """Return the winning ModelResult object, if any."""
        for r in self.results:
            if r.name == self.best_model:
                return r
        return None

    def successful(self) -> list[ModelResult]:
        """Models that trained without error."""
        return [r for r in self.results if not r.failed]
