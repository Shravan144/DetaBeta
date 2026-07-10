"""
Demo: Engine 8 (Explainability) on the passengers dataset.

Run from the backend/ directory with the venv active:

    python demo_engine8.py

It chains Engines 6 -> 7 -> 8: plan a model, train it, then explain the winner
both globally (which features matter) and locally (why specific rows predicted
as they did).
"""

from __future__ import annotations

import pandas as pd

from engines.explainability import explain_model


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")
    target = "survived"

    print("=" * 70)
    print(f"ENGINE 8 - EXPLAINABILITY  (target = '{target}')")
    print("=" * 70)

    report = explain_model(df, target=target, n_examples=3)

    print(f"\nModel explained : {report.model_name}")
    print(f"Problem type    : {report.problem_type}")
    print(f"Base {report.primary_metric:<11}: {report.base_score:.4f}")

    print("\n" + "-" * 70)
    print("GLOBAL FEATURE IMPORTANCE (permutation)")
    print("-" * 70)
    for fi in report.global_importances:
        bar = "#" * int(round(fi.share * 30))
        print(f"  {fi.feature:<16} {fi.importance:+.4f}  {bar}")
        print(f"       -> {fi.reasoning}")

    print("\n" + "-" * 70)
    print("LOCAL EXPLANATIONS (why these specific rows?)")
    print("-" * 70)
    for ex in report.examples:
        print(f"\n  Row {ex.row_index}: predicted {ex.predicted_label!r}", end="")
        if ex.predicted_probability is not None:
            print(f"  (p = {ex.predicted_probability:.3f})", end="")
        print()
        print(f"    {ex.summary}")
        for c in ex.contributions[:4]:
            print(f"      - {c.reasoning}")

    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"  {report.summary}")
    for w in report.warnings:
        print(f"  [note] {w}")


if __name__ == "__main__":
    main()
