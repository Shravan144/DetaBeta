"""
Demo runner for Engine 5 (Feature Lab).

Run it:
    cd backend && source ../.venv/bin/activate && python demo_engine5.py

It profiles a dataset with Engine 1, then asks Engine 5 how the data could be
improved for modelling -- printing each ranked recommendation with its reason,
evidence and a copy-paste code snippet.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.feature_lab import recommend_features, Priority


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")

    print("=" * 70)
    print("ENGINE 5: FEATURE LAB  --  'How can this data be improved?'")
    print("=" * 70)
    print(f"Dataset: {df.shape[0]} rows x {df.shape[1]} columns\n")

    profile = understand_dataset(df)
    report = recommend_features(df, profile=profile, target="survived")

    print("SUMMARY")
    print("-" * 70)
    for line in report.summary:
        print(f"  - {line}")
    print()

    # Group the output by priority tier so the ordering is obvious.
    for tier in (Priority.ESSENTIAL, Priority.RECOMMENDED, Priority.OPTIONAL):
        tier_recs = report.by_priority(tier)
        if not tier_recs:
            continue
        print("=" * 70)
        print(f"{tier.value.upper()}  ({len(tier_recs)})")
        print("=" * 70)
        for i, rec in enumerate(tier_recs, 1):
            cols = ", ".join(rec.columns)
            print(f"\n[{i}] {rec.title}")
            print(f"    transform : {rec.transform.value}")
            print(f"    column(s) : {cols}")
            if rec.evidence:
                print(f"    evidence  : {rec.evidence}")
            for reason in rec.reasoning:
                print(f"    why       : {reason}")
            for warn in rec.warnings:
                print(f"    warning   : {warn}")
            if rec.new_feature_hint:
                print(f"    new feature: {rec.new_feature_hint}")
            if rec.code_snippet:
                print("    code:")
                for code_line in rec.code_snippet.splitlines():
                    print(f"        {code_line}")
    print()


if __name__ == "__main__":
    main()
