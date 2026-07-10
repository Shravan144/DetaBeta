"""
Type definitions for the Feature Lab Engine (Engine 5).

This module is "just data" -- no logic. It defines the vocabulary the engine
uses to describe *how a dataset could be improved* before modelling.

Why a whole engine for this?
----------------------------
Raw columns are rarely in the best shape for a model. A price column with a
long right tail confuses linear models; a text category can't be fed to maths
at all; a date is useless until you pull out "day of week" or "month". The
craft of turning raw columns into model-ready *features* is called feature
engineering, and it is often what separates a mediocre model from a good one.

DetaBeta's rule (from the project doc) is "recommend, don't force". So this
engine NEVER edits your data. It produces a ranked list of *recommendations*,
each carrying:
    - what to do (a TransformType)
    - which column(s) it applies to
    - WHY, in plain language (the reasoning trail)
    - the evidence that triggered it (numbers, not vibes)
    - a copy-paste pandas/sklearn snippet so the user can learn the mechanics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TransformType(str, Enum):
    """The kind of feature transformation being recommended."""

    # Numeric shape fixes
    LOG_TRANSFORM = "log_transform"          # tame a long right tail
    SQRT_TRANSFORM = "sqrt_transform"        # gentler tail fix / count data
    STANDARD_SCALE = "standard_scale"        # center to mean 0, std 1 (z-score)
    MINMAX_SCALE = "minmax_scale"            # squash to a 0..1 range
    CLIP_OUTLIERS = "clip_outliers"          # cap extreme values (winsorize)
    BIN_NUMERIC = "bin_numeric"              # group a number into ranges/buckets

    # Categorical encodings (turn labels into numbers a model can use)
    ONE_HOT_ENCODE = "one_hot_encode"        # few categories -> 0/1 columns
    ORDINAL_ENCODE = "ordinal_encode"        # ordered categories -> ranks
    FREQUENCY_ENCODE = "frequency_encode"    # many categories -> how common each is
    GROUP_RARE_CATEGORIES = "group_rare"     # fold rare labels into "Other"

    # Datetime expansion
    EXTRACT_DATETIME_PARTS = "extract_datetime_parts"  # -> year/month/dow/etc.

    # Structural cleanups aimed at modelling
    DROP_COLUMN = "drop_column"              # leakage / zero-information columns
    TEXT_FEATURE = "text_feature"            # free text needs NLP-style handling


class Priority(str, Enum):
    """
    How strongly we recommend a transform.

    ESSENTIAL : a model will misbehave or error without it (e.g. a raw text
                category cannot be fed to most models at all).
    RECOMMENDED: solid, evidence-backed improvement most people should apply.
    OPTIONAL  : situational; may help some model families, may not matter.
    """

    ESSENTIAL = "essential"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


# Sort weight so the engine can rank ESSENTIAL above OPTIONAL.
PRIORITY_WEIGHT: dict[Priority, int] = {
    Priority.ESSENTIAL: 3,
    Priority.RECOMMENDED: 2,
    Priority.OPTIONAL: 1,
}


@dataclass
class FeatureRecommendation:
    """
    A single, evidence-backed suggestion for improving one (or more) columns.

    The `reasoning` + `evidence` + `code_snippet` trio is the teaching heart of
    this engine: what to do, why it helps, and exactly how to do it.
    """

    transform: TransformType
    columns: list[str]                       # column(s) this applies to
    priority: Priority
    title: str                               # short human headline
    reasoning: list[str] = field(default_factory=list)   # the "why", step by step
    evidence: dict[str, Any] = field(default_factory=dict)  # the numbers behind it
    new_feature_hint: str | None = None      # e.g. "fare_log", "signup_month"
    code_snippet: str | None = None          # copy-paste pandas/sklearn example
    warnings: list[str] = field(default_factory=list)     # caveats / gotchas

    def add_reason(self, reason: str) -> None:
        self.reasoning.append(reason)


@dataclass
class FeatureLabReport:
    """Everything Engine 5 concluded about how to improve the dataset."""

    n_rows: int
    n_cols: int
    target: str | None = None                # optional modelling target column
    recommendations: list[FeatureRecommendation] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)   # plain-language headlines

    def by_priority(self, priority: Priority) -> list[FeatureRecommendation]:
        return [r for r in self.recommendations if r.priority == priority]

    def for_column(self, name: str) -> list[FeatureRecommendation]:
        return [r for r in self.recommendations if name in r.columns]
