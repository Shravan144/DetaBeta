"""
Demo for Engine 7: Experiment Studio.

Run from the backend/ directory:
    python demo_engine7.py

It trains the models Engine 6 recommended for the passengers dataset and prints
an honest, cross-validated comparison -- including whether the fancier models
actually beat the simple baseline.
"""

from __future__ import annotations

import pandas as pd

from engines.experiment_studio import run_experiment


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")
    target = "survived"

    print("=" * 70)
    print(f"ENGINE 7: EXPERIMENT STUDIO  --  predicting '{target}'")
    print("=" * 70)

    report = run_experiment(df, target=target)

    print(f"\nProblem type : {report.problem_type}")
    print(f"Primary metric: {report.primary_metric}")
    print(f"Rows used    : {report.n_rows_used}")
    print(f"Features used: {report.n_features_used}")

    print("\n" + "-" * 70)
    print("MODEL LEADERBOARD")
    print("-" * 70)
    for r in report.results:
        if r.failed:
            print(f"\n  {r.name}: FAILED -- {r.error}")
            continue
        badge = " [baseline]" if r.is_baseline else ""
        crown = "  <-- BEST" if r.name == report.best_model else ""
        print(f"\n  {r.name}{badge}{crown}")
        for m in r.metrics.values():
            print(f"      {m.name:<10} {m.display()}")
        print(f"      trained in {r.train_seconds:.3f}s")

    print("\n" + "-" * 70)
    print("VERDICT")
    print("-" * 70)
    for line in report.best_reasoning:
        print(f"  - {line}")
    if report.baseline_comparison:
        print(f"\n  Baseline check: {report.baseline_comparison}")

    if report.warnings:
        print("\n  Warnings:")
        for w in report.warnings:
            print(f"    ! {w}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(report.summary)


if __name__ == "__main__":
    main()
