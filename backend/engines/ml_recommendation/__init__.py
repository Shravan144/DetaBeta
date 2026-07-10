"""
Engine 6: ML Recommendation -- public API.

Answers: "What should I model, and how?"

This engine plans; it does not train (that is Engine 7). Typical use:

    from engines.ml_recommendation import recommend_model
    report = recommend_model(df, target="survived")
    print(report.problem_type)          # ProblemType.BINARY_CLASSIFICATION
    for algo in report.algorithms:
        print(algo.rank, algo.name, algo.reasoning)
"""

from .engine import recommend_model
from .recommend import (
    detect_problem_type,
    plan_validation,
    recommend_algorithms,
    select_features,
)
from .types import (
    AlgorithmSuggestion,
    Complexity,
    MLRecommendationReport,
    ProblemType,
    ValidationPlan,
)

__all__ = [
    "recommend_model",
    "detect_problem_type",
    "select_features",
    "recommend_algorithms",
    "plan_validation",
    "MLRecommendationReport",
    "ProblemType",
    "Complexity",
    "AlgorithmSuggestion",
    "ValidationPlan",
]
