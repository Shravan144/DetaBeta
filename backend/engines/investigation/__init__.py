"""
Investigation Engine (Engine 3).

Answers: "What interesting things exist?"

Public API:
    investigate(df, profile=None, target=None) -> InvestigationReport

Finds and ranks candidate discoveries -- correlations, group differences,
target relationships, skew and dominant categories -- each with evidence and
reasoning. It reports *leads*, not proof: significance testing is Engine 4's
job, so findings carry a needs_significance_test flag.
"""

from .engine import investigate
from .types import (
    Finding,
    FindingType,
    InvestigationReport,
    Strength,
)

__all__ = [
    "investigate",
    "InvestigationReport",
    "Finding",
    "FindingType",
    "Strength",
]
