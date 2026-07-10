"""
Engine 8: Explainability.

Answers: "Why did the model predict this?"

Opens the black box of the winning model with two transparent, model-agnostic
techniques:
  - permutation importance (global: which features matter overall)
  - occlusion / what-if (local: why a single prediction came out as it did)

Public API:
    from engines.explainability import explain_model
    report = explain_model(df, target="survived")
"""

from .engine import explain_model
from .types import (
    ExplainabilityReport,
    FeatureContribution,
    FeatureImportance,
    PredictionExplanation,
)

__all__ = [
    "explain_model",
    "ExplainabilityReport",
    "FeatureImportance",
    "FeatureContribution",
    "PredictionExplanation",
]
