"""
Engine 4: Statistics -- public API.

Answers: "Are these findings statistically meaningful?"

Typical use:
    from engines.statistics import analyze_significance
    report = analyze_significance(df, target="survived")
    for t in report.significant():
        print(t.title, t.p_value, t.effect_size)
"""

from .engine import analyze_significance
from .tests import chi_square_test, correlation_test, group_difference_test
from .types import (
    EffectSize,
    Significance,
    StatisticsReport,
    StatTest,
    TestKind,
)

__all__ = [
    "analyze_significance",
    "correlation_test",
    "group_difference_test",
    "chi_square_test",
    "StatisticsReport",
    "StatTest",
    "TestKind",
    "Significance",
    "EffectSize",
]
