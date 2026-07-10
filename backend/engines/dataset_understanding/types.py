"""
Type definitions for the Dataset Understanding Engine (Engine 1).

This module is intentionally "just data" -- it contains no logic. It defines
the *vocabulary* the rest of the engine uses to describe a dataset:

  - SemanticType : the human-meaningful kind of a column (not the raw dtype)
  - ColumnProfile: everything we learned about a single column
  - DatasetProfile: everything we learned about the whole dataset

Why separate "semantic type" from pandas' dtype?
--------------------------------------------------
pandas tells you the *storage* type ("int64", "object", "float64").
But storage type is not meaning. Consider:

    survived        -> stored as int64, but it is really a BINARY category (0/1)
    passenger_id    -> stored as int64, but it is really an IDENTIFIER, not a number
    ticket_price    -> stored as float64, and it really is CONTINUOUS numeric
    embarked_port   -> stored as object, and it really is a CATEGORICAL

If we treated `survived` and `ticket_price` the same just because both are
numbers, every later engine (stats, ML, plots) would make wrong decisions.
So Engine 1's whole job is to add *meaning* on top of raw dtype.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SemanticType(str, Enum):
    """
    The meaning-level category of a column.

    We inherit from `str` so these values serialize cleanly to JSON later
    (SemanticType.NUMERIC_CONTINUOUS becomes the string "numeric_continuous").
    """

    # Numbers that can take (effectively) any value in a range: price, age, height.
    NUMERIC_CONTINUOUS = "numeric_continuous"

    # Whole-number counts with limited distinct values: number_of_siblings, rooms.
    NUMERIC_DISCRETE = "numeric_discrete"

    # Exactly two categories: yes/no, 0/1, true/false, male/female.
    BINARY = "binary"

    # A small set of labels with no inherent order: country, color, product_type.
    CATEGORICAL = "categorical"

    # Dates / timestamps.
    DATETIME = "datetime"

    # Free-form text with many unique values: reviews, names, descriptions.
    TEXT = "text"

    # A unique key per row: id, uuid, ticket number. Useless for modelling.
    IDENTIFIER = "identifier"

    # Every value is the same (or all missing). Carries zero information.
    CONSTANT = "constant"

    # We genuinely could not decide with confidence.
    UNKNOWN = "unknown"


@dataclass
class ColumnProfile:
    """
    Everything Engine 1 learned about ONE column.

    Notice the `reasoning` field: this is the heart of DetaBeta's philosophy.
    We never just say "this is categorical" -- we always record *why*, so the
    UI can teach the user instead of hiding the decision.
    """

    name: str
    raw_dtype: str                       # what pandas stored it as, e.g. "int64"
    semantic_type: SemanticType          # what we decided it MEANS
    reasoning: list[str] = field(default_factory=list)  # the "why", step by step

    # Universal counts (apply to every column type)
    n_total: int = 0
    n_missing: int = 0
    missing_pct: float = 0.0
    n_unique: int = 0
    unique_pct: float = 0.0

    # A few example values so a human can eyeball the column
    sample_values: list[Any] = field(default_factory=list)

    # Type-specific extra stats (min/max/mean for numbers, top categories, etc.)
    # Kept as a free-form dict so each type can attach what makes sense for it.
    stats: dict[str, Any] = field(default_factory=dict)

    def add_reason(self, reason: str) -> None:
        """Append a single human-readable reason to the decision trail."""
        self.reasoning.append(reason)


@dataclass
class DatasetProfile:
    """
    Everything Engine 1 learned about the WHOLE dataset.

    This is the object every later engine and every UI screen consumes.
    """

    n_rows: int
    n_cols: int
    columns: list[ColumnProfile] = field(default_factory=list)

    # Dataset-level observations, e.g. "3 columns look like identifiers".
    observations: list[str] = field(default_factory=list)

    # Convenience roll-ups so callers don't have to recompute them.
    memory_usage_bytes: int = 0
    n_duplicate_rows: int = 0

    def column(self, name: str) -> ColumnProfile | None:
        """Look up a single column profile by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def columns_of_type(self, semantic_type: SemanticType) -> list[ColumnProfile]:
        """Return all columns matching a given semantic type."""
        return [c for c in self.columns if c.semantic_type == semantic_type]
