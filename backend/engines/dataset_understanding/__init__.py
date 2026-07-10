"""
Dataset Understanding Engine (Engine 1).

Answers: "What kind of data is this?"

Public API:
    understand_dataset(df) -> DatasetProfile
    SemanticType, ColumnProfile, DatasetProfile
"""

from .engine import understand_dataset
from .types import ColumnProfile, DatasetProfile, SemanticType

__all__ = [
    "understand_dataset",
    "DatasetProfile",
    "ColumnProfile",
    "SemanticType",
]
