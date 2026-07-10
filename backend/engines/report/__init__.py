"""
Engine 9: Report -- the capstone.

Public API:

    from engines.report import generate_report
    story = generate_report(df, target="survived", dataset_name="Passengers")

It runs Engines 1-8 and composes their results into a single `DataStory`: an
ordered, plain-language narrative answering "What should another human learn
from this?"
"""

from .engine import generate_report
from .types import DataStory, ReportSection

__all__ = ["generate_report", "DataStory", "ReportSection"]
