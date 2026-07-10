"""
Engine 9: Report -- "What should another human learn from this?"

This is the capstone engine. It runs the entire DetaBeta pipeline (Engines 1-8)
and composes their outputs into a single, ordered, plain-language narrative: a
`DataStory` a human can read top to bottom.

Design notes
------------
* Engine 9 performs NO new data analysis. It orchestrates the other engines and
  narrates their results (the narration lives in composer.py).
* It is resilient: the ML stages (6-8) need a target column and can fail on tiny
  or degenerate data. If they cannot run, the story still includes the
  data-understanding-through-statistics chapters and says so honestly.
* Every verdict (trust level, headline finding, model verdict) is stated in
  plain language with caveats, matching DetaBeta's philosophy.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.data_health import assess_health
from engines.investigation import investigate
from engines.statistics import analyze_significance
from engines.feature_lab import recommend_features
from engines.ml_recommendation import recommend_model
from engines.experiment_studio import run_experiment
from engines.explainability import explain_model
from engines.statistics.types import Significance

from .types import DataStory
from . import composer


def generate_report(
    df: pd.DataFrame,
    *,
    target: str | None = None,
    dataset_name: str = "dataset",
) -> DataStory:
    """
    Run the full pipeline and compose the final narrative.

    Args:
        df: the raw dataset.
        target: optional column to model. Sections 6-8 only run if it is given
            and the modelling actually succeeds.
        dataset_name: a friendly name used in the report title.

    Returns:
        A `DataStory` -- the ordered, plain-language capstone report.
    """
    story = DataStory(
        title=f"Data Story: {dataset_name}",
        dataset_name=dataset_name,
        target=target,
    )

    # --- Analysis half (always runs) : Engines 1-5 -----------------------
    profile = understand_dataset(df)
    health = assess_health(df)
    investigation = investigate(df, target=target)
    stats = analyze_significance(df, target=target)
    features = recommend_features(df, target=target)

    story.sections.append(composer.compose_understanding(profile))
    story.sections.append(composer.compose_health(health))
    story.sections.append(composer.compose_investigation(investigation))
    story.sections.append(composer.compose_evidence(stats))
    story.sections.append(composer.compose_features(features))

    # --- Modelling half (only with a target, and only if it runs) --------
    experiment = None
    if target is not None and target in df.columns:
        try:
            plan = recommend_model(df, target=target)
            experiment = run_experiment(df, target=target)
            story.sections.append(composer.compose_modelling(plan, experiment))

            # Explainability needs a successfully trained winner.
            if experiment.best() is not None:
                try:
                    explain = explain_model(df, target=target)
                    story.sections.append(
                        composer.compose_explainability(explain)
                    )
                except Exception as exc:  # noqa: BLE001 - stay resilient
                    story.caveats.append(
                        f"Model explanations could not be generated ({exc})."
                    )
        except Exception as exc:  # noqa: BLE001 - stay resilient
            story.caveats.append(
                f"Modelling could not be completed for target '{target}' ({exc}). "
                f"The analysis chapters above are unaffected."
            )
    else:
        story.caveats.append(
            "No target column was provided, so the modelling and explainability "
            "chapters were skipped. Provide a target to model an outcome."
        )

    # --- Honest headline verdicts ----------------------------------------
    story.trust_level = f"{_trust_word(health.score)} (grade {health.grade})"

    sig = stats.significant()
    if sig:
        top = sig[0]
        effect = top.effect_size.value if top.effect_size else "unknown"
        story.headline_finding = (
            f"{top.title} (statistically significant, {effect} effect)."
        )
    else:
        story.headline_finding = (
            "No pattern reached statistical significance -- likely too little "
            "data to confirm anything with confidence."
        )

    if experiment is not None and experiment.best() is not None:
        best = experiment.best()
        verdict = (
            f"{experiment.best_model}: {experiment.primary_metric} "
            f"{best.primary_score:.3f}"
        )
        verdict += (
            " (beats the simple baseline)"
            if experiment.beat_baseline
            else " (no better than the simple baseline)"
        )
        story.model_verdict = verdict

    # --- Executive summary (a 20-second read) ----------------------------
    story.executive_summary = _build_executive_summary(
        profile, health, stats, story
    )

    # --- Caveats gathered from the pipeline ------------------------------
    if profile.n_rows < 100:
        story.caveats.append(
            f"The dataset is small ({profile.n_rows} rows); all conclusions "
            f"should be treated as tentative until more data is available."
        )
    if stats.bonferroni_alpha is not None and not [
        t for t in sig if t.p_value < stats.bonferroni_alpha
    ]:
        story.caveats.append(
            "No result survived correction for multiple comparisons, so even "
            "the significant findings warrant a second look."
        )

    # --- Concrete next steps ---------------------------------------------
    story.next_steps = _build_next_steps(health, features, experiment)

    return story


# --------------------------------------------------------------------------
# Small private helpers
# --------------------------------------------------------------------------
def _trust_word(score: float) -> str:
    if score >= 85:
        return "Trustworthy"
    if score >= 70:
        return "Mostly trustworthy"
    if score >= 50:
        return "Use with caution"
    return "Fragile"


def _build_executive_summary(profile, health, stats, story) -> list[str]:
    lines: list[str] = []
    lines.append(
        f"This {profile.n_rows}-row, {profile.n_cols}-column dataset is "
        f"{story.trust_level.lower()}."
    )
    lines.append(story.headline_finding)
    if story.model_verdict:
        lines.append(f"Best model -- {story.model_verdict}.")
    return lines


def _build_next_steps(health, features, experiment) -> list[str]:
    steps: list[str] = []

    # 1. Fix the most severe health issues first.
    severe = [
        i
        for i in health.issues
        if i.severity.value in ("critical", "high")
    ]
    if severe:
        steps.append(
            f"Address the {len(severe)} most severe data-quality issue(s) "
            f"before trusting any conclusion."
        )

    # 2. Apply essential feature preparation.
    from engines.feature_lab.types import Priority

    essential = features.by_priority(Priority.ESSENTIAL)
    if essential:
        steps.append(
            f"Apply the {len(essential)} essential data-preparation step(s) "
            f"(e.g. {essential[0].title})."
        )

    # 3. Modelling guidance.
    if experiment is not None and experiment.best() is not None:
        if not experiment.beat_baseline:
            steps.append(
                "Prefer the simple baseline model -- added complexity did not "
                "improve results here."
            )
        else:
            steps.append(
                f"Investigate '{experiment.best_model}' further and validate it "
                f"on fresh, unseen data before relying on it."
            )
    else:
        steps.append(
            "Collect more data and provide a target column to enable modelling."
        )

    return steps
