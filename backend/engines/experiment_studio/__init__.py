"""
Engine 7: Experiment Studio -- public API.

Answers: "Which model performs best?"

This engine actually trains the models Engine 6 recommended and reports honest,
cross-validated scores. Typical use:

    from engines.experiment_studio import run_experiment
    report = run_experiment(df, target="survived")
    print(report.best_model)          # e.g. "Logistic Regression"
    print(report.baseline_comparison) # did complexity pay off?
    for r in report.results:
        print(r.name, r.primary_metric, r.primary_score)
"""

from .engine import run_experiment
from .types import ExperimentReport, MetricScore, ModelResult

__all__ = [
    "run_experiment",
    "ExperimentReport",
    "ModelResult",
    "MetricScore",
]
