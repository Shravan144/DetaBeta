"""
The composer for Engine 9 (Report).

Each function here takes the structured output of one earlier engine and turns
it into a human-readable `ReportSection`. There is deliberately NO new analysis
in this file -- we only re-tell what the engines already found. Keeping the
"narration" separate from the "computation" is a clean-architecture habit worth
learning: the engines decide truth, the composer decides how to say it.
"""

from __future__ import annotations

from engines.dataset_understanding.types import DatasetProfile, SemanticType
from engines.data_health.types import HealthReport, Severity
from engines.investigation.types import InvestigationReport
from engines.statistics.types import StatisticsReport, Significance
from engines.feature_lab.types import FeatureLabReport, Priority
from engines.ml_recommendation.types import MLRecommendationReport
from engines.experiment_studio.types import ExperimentReport
from engines.explainability.types import ExplainabilityReport

from .types import ReportSection


def _plural(n: int, word: str) -> str:
    """Tiny helper: '1 column' vs '3 columns'."""
    return f"{n} {word}" + ("" if n == 1 else "s")


# --------------------------------------------------------------------------
# Section 1 -- Understanding (Engine 1)
# --------------------------------------------------------------------------
def compose_understanding(profile: DatasetProfile) -> ReportSection:
    # Count columns by the meaning Engine 1 assigned them.
    by_type: dict[SemanticType, int] = {}
    for col in profile.columns:
        by_type[col.semantic_type] = by_type.get(col.semantic_type, 0) + 1

    n_numeric = sum(
        by_type.get(t, 0)
        for t in (SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE)
    )
    n_categorical = by_type.get(SemanticType.CATEGORICAL, 0) + by_type.get(
        SemanticType.BINARY, 0
    )
    n_ids = by_type.get(SemanticType.IDENTIFIER, 0)

    section = ReportSection(
        key="understanding",
        title="What is this data?",
        headline=(
            f"A dataset of {_plural(profile.n_rows, 'row')} and "
            f"{_plural(profile.n_cols, 'column')}: "
            f"{n_numeric} numeric, {n_categorical} categorical."
        ),
    )
    section.add(
        f"The dataset contains {_plural(profile.n_rows, 'row')} described by "
        f"{_plural(profile.n_cols, 'column')}. Rather than trusting how the "
        f"values are stored, each column was classified by what it actually "
        f"MEANS: {n_numeric} numeric, {n_categorical} categorical, and "
        f"{n_ids} identifier-like."
    )
    for obs in profile.observations[:4]:
        section.point(obs)
    if n_ids:
        section.point(
            f"{_plural(n_ids, 'column')} look like identifiers and should be "
            f"kept out of any model to avoid leakage."
        )
    return section


# --------------------------------------------------------------------------
# Section 2 -- Health (Engine 2)
# --------------------------------------------------------------------------
def compose_health(health: HealthReport) -> ReportSection:
    critical = health.issues_by_severity(Severity.CRITICAL)
    high = health.issues_by_severity(Severity.HIGH)

    section = ReportSection(
        key="health",
        title="Can I trust this data?",
        headline=f"Health score {health.score:.0f}/100 (grade {health.grade}).",
    )
    section.add(
        f"Overall data health scored {health.score:.0f} out of 100 (grade "
        f"{health.grade}), based on {_plural(len(health.issues), 'issue')} "
        f"found across missing values, duplicates, outliers and consistency."
    )
    if critical or high:
        section.add(
            f"The most pressing concerns are "
            f"{_plural(len(critical), 'critical issue')} and "
            f"{_plural(len(high), 'high-severity issue')} that should be "
            f"addressed before drawing firm conclusions."
        )
    else:
        section.add(
            "No critical or high-severity issues were found; the data is in "
            "reasonable shape to analyse."
        )
    for issue in (critical + high)[:4]:
        section.point(issue.title)
    return section


# --------------------------------------------------------------------------
# Section 3 -- Investigation (Engine 3)
# --------------------------------------------------------------------------
def compose_investigation(investigation: InvestigationReport) -> ReportSection:
    top = investigation.top(4)
    section = ReportSection(
        key="investigation",
        title="What is interesting in it?",
        headline=(
            f"{_plural(investigation.n_findings, 'candidate pattern')} surfaced "
            f"for a closer look."
        ),
    )
    section.add(
        f"Exploration surfaced {_plural(investigation.n_findings, 'candidate pattern')}"
        f" -- correlations, group differences and skewed distributions worth "
        f"investigating. These are leads, not proof; each was passed to the "
        f"statistics stage for confirmation."
    )
    for f in top:
        section.point(f"{f.title} (strength: {f.strength.value}).")
    return section


# --------------------------------------------------------------------------
# Section 4 -- Evidence / Statistics (Engine 4)
# --------------------------------------------------------------------------
def compose_evidence(stats: StatisticsReport) -> ReportSection:
    sig = stats.significant()
    section = ReportSection(
        key="evidence",
        title="What held up under scrutiny?",
        headline=(
            f"{_plural(len(sig), 'pattern')} proved statistically significant "
            f"out of {_plural(stats.n_tests, 'test')}."
        ),
    )
    section.add(
        f"{_plural(stats.n_tests, 'statistical test')} were run at a "
        f"significance threshold of {stats.alpha}. Of these, "
        f"{_plural(len(sig), 'result')} were statistically significant -- "
        f"unlikely to be explained by random chance alone."
    )
    if stats.bonferroni_alpha is not None:
        survivors = [t for t in sig if t.p_value < stats.bonferroni_alpha]
        section.add(
            f"After correcting for running many tests at once (a stricter "
            f"threshold of {stats.bonferroni_alpha:.4f}), "
            f"{_plural(len(survivors), 'result')} remained convincing. This "
            f"guards against being fooled by luck when many things are tested."
        )
    for t in sig[:4]:
        effect = t.effect_size.value if t.effect_size else "unknown"
        section.point(f"{t.title}: p={t.p_value:.4f}, effect size {effect}.")
    return section


# --------------------------------------------------------------------------
# Section 5 -- Feature Lab (Engine 5)
# --------------------------------------------------------------------------
def compose_features(features: FeatureLabReport) -> ReportSection:
    essential = features.by_priority(Priority.ESSENTIAL)
    section = ReportSection(
        key="features",
        title="How should the data be prepared?",
        headline=(
            f"{_plural(len(features.recommendations), 'preparation step')} "
            f"recommended ({_plural(len(essential), 'essential')})."
        ),
    )
    section.add(
        f"To get the data model-ready, "
        f"{_plural(len(features.recommendations), 'transformation')} were "
        f"recommended, of which {_plural(len(essential), 'is')} essential. "
        f"Nothing was applied automatically -- these are suggestions with the "
        f"reasoning and code needed to apply them."
    )
    for rec in essential[:4]:
        section.point(rec.title)
    return section


# --------------------------------------------------------------------------
# Section 6 + 7 -- Modelling plan (Engine 6) and results (Engine 7)
# --------------------------------------------------------------------------
def compose_modelling(
    plan: MLRecommendationReport, experiment: ExperimentReport
) -> ReportSection:
    section = ReportSection(
        key="modelling",
        title="What did modelling reveal?",
        headline=(
            f"{experiment.best_model} won on {experiment.problem_type} "
            f"({experiment.primary_metric} "
            f"{experiment.best().primary_score:.3f})."
            if experiment.best()
            else "No model could be trained reliably."
        ),
    )
    section.add(
        f"The target '{plan.target}' defines a {plan.problem_type.value} "
        f"problem, evaluated with "
        f"{plan.validation.strategy if plan.validation else 'cross-validation'}."
    )
    best = experiment.best()
    if best:
        section.add(
            f"After training {_plural(len(experiment.successful()), 'candidate model')}"
            f" on identical folds, '{experiment.best_model}' performed best "
            f"({experiment.primary_metric} = {best.primary_score:.3f}). "
            f"{experiment.baseline_comparison}"
        )
        section.point(
            f"Winner: {experiment.best_model} "
            f"({experiment.primary_metric} {best.primary_score:.3f})."
        )
        section.point(
            "A complex model beat the simple baseline."
            if experiment.beat_baseline
            else "The simple baseline was competitive -- prefer it for its simplicity."
        )
    return section


# --------------------------------------------------------------------------
# Section 8 -- Explainability (Engine 8)
# --------------------------------------------------------------------------
def compose_explainability(explain: ExplainabilityReport) -> ReportSection:
    top = explain.top_features(4)
    section = ReportSection(
        key="explainability",
        title="Why does the model decide what it does?",
        headline=(
            f"'{top[0].feature}' is the most influential feature "
            f"({top[0].share * 100:.0f}% of the signal)."
            if top
            else "Model behaviour could not be explained."
        ),
    )
    if top:
        section.add(
            f"The winning model's decisions are driven mostly by "
            f"'{top[0].feature}', which accounts for about "
            f"{top[0].share * 100:.0f}% of its predictive signal. Understanding "
            f"this lets a human sanity-check whether the model is relying on "
            f"sensible information rather than noise or leakage."
        )
        for imp in top:
            section.point(
                f"{imp.feature}: {imp.share * 100:.0f}% of the model's signal."
            )
    return section
