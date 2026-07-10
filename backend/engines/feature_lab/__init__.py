"""
Feature Lab Engine (Engine 5).

Public API:
    recommend_features(df, profile=None, target=None) -> FeatureLabReport

Answers "How can this data be improved?" by producing a ranked, evidence-backed
list of feature-engineering recommendations (log/scale/encode/bin/extract/drop),
each with a plain-language reason and a copy-paste code snippet. It never
modifies the data -- it only advises.
"""

from .engine import recommend_features
from .types import (
    FeatureLabReport,
    FeatureRecommendation,
    Priority,
    TransformType,
)

__all__ = [
    "recommend_features",
    "FeatureLabReport",
    "FeatureRecommendation",
    "Priority",
    "TransformType",
]
