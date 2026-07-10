"""
Type definitions for the ML Recommendation Engine (Engine 6).

Answers: "What should I model, and how?"

This engine does NOT train anything. It is the *planning* stage that sits
between data preparation (Engines 1-5) and actual model training (Engine 7).
Its job is to look at the target column and the features, then reason about:

  1. What KIND of problem is this?      -> ProblemType
  2. Which algorithms are sensible?     -> AlgorithmSuggestion (with evidence)
  3. How should we validate honestly?   -> ValidationPlan
  4. What could go wrong / leak?        -> risks / warnings

Everything carries a `reasoning` trail, matching DetaBeta's philosophy:
never recommend an algorithm without saying *why*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProblemType(str, Enum):
    """The kind of supervised-learning problem the target implies."""

    # Predict one of exactly two classes: churn / no-churn, survived / died.
    BINARY_CLASSIFICATION = "binary_classification"

    # Predict one of 3+ unordered classes: species, product category.
    MULTICLASS_CLASSIFICATION = "multiclass_classification"

    # Predict a continuous number: price, temperature, revenue.
    REGRESSION = "regression"

    # We could not confidently decide (e.g. no usable target given).
    UNKNOWN = "unknown"


class Complexity(str, Enum):
    """How complex/interpretable an algorithm is -- a teaching signal."""

    SIMPLE = "simple"        # easy to explain, great baseline
    MODERATE = "moderate"    # more power, still reasonable to reason about
    ADVANCED = "advanced"    # highest power, hardest to interpret


@dataclass
class AlgorithmSuggestion:
    """
    One recommended algorithm, with the evidence for recommending it.

    `rank` orders suggestions (1 = try first). `is_baseline` marks the simple
    model you should always compare against, so "fancy" models have to earn
    their complexity.
    """

    name: str                                  # e.g. "Logistic Regression"
    rank: int                                  # 1 = recommended starting point
    complexity: Complexity
    is_baseline: bool = False
    reasoning: list[str] = field(default_factory=list)   # WHY this algorithm
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    # sklearn import path we will actually use in Engine 7, shown for learning.
    sklearn_path: str = ""


@dataclass
class ValidationPlan:
    """
    How to evaluate models honestly.

    The single most common beginner mistake is judging a model on the same
    data it trained on. This plan makes the correct approach explicit.
    """

    strategy: str                    # e.g. "Stratified 5-fold cross-validation"
    test_size: float = 0.2           # fraction held out if a simple split is used
    n_folds: int = 5
    stratify: bool = False           # keep class balance across folds?
    primary_metric: str = ""         # the metric to optimize
    other_metrics: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)


@dataclass
class MLRecommendationReport:
    """The full modelling plan produced by Engine 6."""

    target: str
    problem_type: ProblemType
    problem_reasoning: list[str] = field(default_factory=list)

    # Which columns to feed the model, and which to leave out (and why).
    feature_columns: list[str] = field(default_factory=list)
    excluded_columns: dict[str, str] = field(default_factory=dict)  # name -> reason

    algorithms: list[AlgorithmSuggestion] = field(default_factory=list)
    validation: ValidationPlan | None = None

    # Honest warnings: class imbalance, leakage risk, tiny dataset, etc.
    warnings: list[str] = field(default_factory=list)

    # One-paragraph plain-language summary for the UI.
    summary: str = ""

    def baseline(self) -> AlgorithmSuggestion | None:
        """Return the baseline algorithm, if one was suggested."""
        for algo in self.algorithms:
            if algo.is_baseline:
                return algo
        return None
