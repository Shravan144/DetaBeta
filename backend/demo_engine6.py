"""
Demo for Engine 6 (ML Recommendation).

Run from the backend/ directory:
    python demo_engine6.py

It builds a modelling plan for predicting `survived` on the passengers data,
showing how Engine 6 reasons about problem type, features, algorithms, and
validation -- all WITHOUT training anything yet.
"""

from __future__ import annotations

import pandas as pd

from engines.ml_recommendation import recommend_model


def _rule(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")
    target = "survived"
    report = recommend_model(df, target=target)

    _rule(f"ENGINE 6: ML RECOMMENDATION  (target = '{target}')")
    print(report.summary)

    _rule("PROBLEM TYPE")
    print(f"-> {report.problem_type.value}")
    for r in report.problem_reasoning:
        print(f"   - {r}")

    _rule("FEATURES")
    print(f"Use ({len(report.feature_columns)}): {', '.join(report.feature_columns)}")
    print("\nExcluded:")
    for name, reason in report.excluded_columns.items():
        print(f"   - {name}: {reason}")

    _rule("RECOMMENDED ALGORITHMS (try in order)")
    for algo in report.algorithms:
        tag = "  [BASELINE]" if algo.is_baseline else ""
        print(f"\n{algo.rank}. {algo.name}  ({algo.complexity.value}){tag}")
        for r in algo.reasoning:
            print(f"     why: {r}")
        print(f"     pros: {', '.join(algo.pros)}")
        print(f"     cons: {', '.join(algo.cons)}")
        print(f"     sklearn: {algo.sklearn_path}")

    _rule("VALIDATION PLAN")
    v = report.validation
    print(f"Strategy: {v.strategy}")
    print(f"Primary metric: {v.primary_metric}")
    print(f"Also report: {', '.join(v.other_metrics)}")
    for r in v.reasoning:
        print(f"   - {r}")

    _rule("WARNINGS")
    if report.warnings:
        for w in report.warnings:
            print(f"   ! {w}")
    else:
        print("   (none)")


if __name__ == "__main__":
    main()
