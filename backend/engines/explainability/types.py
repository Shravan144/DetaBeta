"""
Type definitions for the Explainability Engine (Engine 8).

Answers: "Why did the model predict this?"

A model that cannot be explained cannot be trusted or taught. This engine opens
the black box in two complementary ways:

  - GLOBAL: which features matter most to the model overall?
            (permutation importance -- shuffle a column and watch the score fall)
  - LOCAL:  for ONE specific prediction, which features pushed it up or down?
            (occlusion / what-if -- replace a feature with its typical value and
             measure how far the prediction moves)

Both techniques are model-agnostic (they work for any model) and map back to the
ORIGINAL human-readable columns, not opaque one-hot-encoded columns. Every number
is paired with a plain-language interpretation, matching DetaBeta's philosophy.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeatureImportance:
    """
    One feature's GLOBAL importance to the model.

    `importance` is the average drop in the model's score when this feature's
    values are randomly shuffled. Bigger drop = the model relied on it more.
    `std` shows how much that drop varied across repeats (a stability signal).
    """

    feature: str
    importance: float
    std: float
    # importance as a share of the total (0..1), for easy "X% of the signal" text.
    share: float = 0.0
    reasoning: str = ""


@dataclass
class FeatureContribution:
    """
    One feature's LOCAL contribution to a SINGLE prediction.

    `value` is the feature's actual value for this row. `effect` is how much the
    prediction changed when we replaced that value with the dataset's typical
    value: positive means this feature pushed the prediction UP (toward the
    positive class / a higher number), negative means it pulled it DOWN.
    """

    feature: str
    value: object
    effect: float
    direction: str = ""      # "increases" | "decreases" | "no effect"
    reasoning: str = ""


@dataclass
class PredictionExplanation:
    """A full explanation of the model's prediction for one row."""

    row_index: int
    predicted_label: object                       # class label or numeric value
    predicted_probability: float | None = None    # for classification, if available
    baseline_prediction: float | None = None      # the "average" starting point
    contributions: list[FeatureContribution] = field(default_factory=list)
    summary: str = ""


@dataclass
class ExplainabilityReport:
    """The full explainability analysis of the winning model."""

    target: str
    model_name: str
    problem_type: str
    primary_metric: str = ""
    base_score: float = 0.0            # the model's score before any shuffling

    global_importances: list[FeatureImportance] = field(default_factory=list)
    examples: list[PredictionExplanation] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    def top_features(self, n: int = 5) -> list[FeatureImportance]:
        """The n most important features, already sorted by the engine."""
        return self.global_importances[:n]
