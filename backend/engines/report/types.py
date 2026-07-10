"""
Type definitions for the Report Engine (Engine 9).

Answers: "What should another human learn from this?"

Engines 1-8 each answered ONE question and produced a rich, structured report.
But a pile of eight reports is not a story. A human who wants to understand a
dataset should be able to read ONE narrative, top to bottom, and come away
knowing: what the data is, whether to trust it, what is interesting in it,
what held up under statistical scrutiny, how to prepare it, what to model,
which model won, and why it made its decisions.

Engine 9 is that narrator. It does NOT compute anything new about the data --
it *composes*. It reads the outputs of the earlier engines and turns them into
an ordered set of plain-language sections, each with:

    - a title           (the question this section answers)
    - a headline        (the single most important takeaway)
    - body paragraphs   (the explanation, in human language)
    - key_points        (scannable bullet takeaways)

This module is "just data": the vocabulary of a finished report. The logic that
fills it lives in composer.py and engine.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReportSection:
    """
    One chapter of the final narrative.

    Each section corresponds to one engine's contribution to the story. The
    `headline` is deliberately a single sentence -- the one thing a busy reader
    should remember even if they skip the body.
    """

    key: str                                 # stable id, e.g. "understanding"
    title: str                               # human title, e.g. "What is this data?"
    headline: str                            # the one-sentence takeaway
    body: list[str] = field(default_factory=list)        # explanatory paragraphs
    key_points: list[str] = field(default_factory=list)  # scannable bullets

    def add(self, paragraph: str) -> None:
        self.body.append(paragraph)

    def point(self, bullet: str) -> None:
        self.key_points.append(bullet)


@dataclass
class DataStory:
    """
    The full narrative Engine 9 produces: the capstone of the whole pipeline.

    `sections` are ordered to be read start-to-finish. `executive_summary` is a
    short standalone paragraph for someone who will not read the details.
    `trust_level` and `confidence` are honest, plain-language verdicts so a
    reader immediately knows how much weight to put on the conclusions.
    """

    title: str
    dataset_name: str
    target: str | None = None

    # A short, standalone overview a reader can grasp in ~20 seconds.
    executive_summary: list[str] = field(default_factory=list)

    # The ordered chapters (one per engine that contributed).
    sections: list[ReportSection] = field(default_factory=list)

    # Honest headline verdicts.
    trust_level: str = ""        # e.g. "Trustworthy (grade B)"
    headline_finding: str = ""   # the single most interesting confirmed result
    model_verdict: str = ""      # e.g. "Random Forest, F1 0.81 (beats baseline)"

    # Caveats a reader must keep in mind (small sample, imbalance, etc.).
    caveats: list[str] = field(default_factory=list)

    # Concrete, prioritized suggestions for what to do next.
    next_steps: list[str] = field(default_factory=list)

    def section(self, key: str) -> ReportSection | None:
        for s in self.sections:
            if s.key == key:
                return s
        return None
