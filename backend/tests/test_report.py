"""
Tests for Engine 9 (Report).

Engine 9 composes; it does not compute new facts. So these tests check that:
  1. the narrative is assembled correctly (right sections, in order),
  2. it degrades gracefully when there is no target (analysis-only story),
  3. the honest verdicts (trust level, caveats, next steps) are populated,
  4. it survives tiny/degenerate data without crashing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engines.report import generate_report


def _make_modellable_df(n: int = 120) -> pd.DataFrame:
    """A dataset with a learnable binary target and a mix of column types."""
    rng = np.random.default_rng(42)
    age = rng.normal(40, 12, n).clip(1, 90)
    income = rng.exponential(50_000, n) + 10_000
    city = rng.choice(["NY", "LA", "CHI", "HOU"], n)
    # Target depends on age + income so a model can actually learn something.
    logit = (age - 40) / 20 + (income - 50_000) / 60_000
    prob = 1 / (1 + np.exp(-logit))
    target = (rng.random(n) < prob).astype(int)
    return pd.DataFrame(
        {"age": age, "income": income, "city": city, "purchased": target}
    )


def test_report_has_all_analysis_sections():
    df = _make_modellable_df()
    story = generate_report(df, target="purchased", dataset_name="Shoppers")

    keys = [s.key for s in story.sections]
    # The five analysis sections must always be present, in order.
    assert keys[:5] == [
        "understanding",
        "health",
        "investigation",
        "evidence",
        "features",
    ]


def test_report_includes_modelling_when_target_given():
    df = _make_modellable_df()
    story = generate_report(df, target="purchased", dataset_name="Shoppers")

    keys = [s.key for s in story.sections]
    assert "modelling" in keys, "expected a modelling section when a target is given"
    # A model verdict string should be populated.
    assert story.model_verdict, "expected a plain-language model verdict"


def test_report_skips_modelling_without_target():
    df = _make_modellable_df()
    story = generate_report(df, dataset_name="Shoppers")  # no target

    keys = [s.key for s in story.sections]
    assert "modelling" not in keys
    assert "explainability" not in keys
    # It should say WHY it skipped, honestly.
    assert any("target" in c.lower() for c in story.caveats)


def test_report_populates_verdicts_and_summary():
    df = _make_modellable_df()
    story = generate_report(df, target="purchased", dataset_name="Shoppers")

    assert story.trust_level, "trust level should be a non-empty verdict"
    assert story.executive_summary, "executive summary should not be empty"
    assert story.headline_finding, "headline finding should be set"
    assert story.next_steps, "there should be at least one recommended next step"


def test_report_flags_small_datasets():
    df = _make_modellable_df(n=30)  # deliberately tiny
    story = generate_report(df, target="purchased", dataset_name="Tiny")
    assert any("small" in c.lower() for c in story.caveats), (
        "a tiny dataset should trigger a small-sample caveat"
    )


def test_report_survives_degenerate_data():
    # All-constant target and a single feature: modelling will likely fail, but
    # the report must still be produced (analysis chapters + honest caveat).
    df = pd.DataFrame({"x": range(40), "y": [1] * 40})
    story = generate_report(df, target="y", dataset_name="Degenerate")
    # Analysis sections still present; no crash.
    assert story.section("understanding") is not None
    assert isinstance(story.next_steps, list)


def test_executive_summary_is_concise():
    df = _make_modellable_df()
    story = generate_report(df, target="purchased", dataset_name="Shoppers")
    # A "20-second read" -- keep it short.
    assert 1 <= len(story.executive_summary) <= 4
