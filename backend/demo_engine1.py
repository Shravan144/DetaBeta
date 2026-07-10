"""
Demo runner for Engine 1 (Dataset Understanding).

Run it from the backend/ folder:

    source ../.venv/bin/activate
    python demo_engine1.py

It loads the sample passengers dataset, runs the engine, and prints a
human-readable report so you can *see* the engine reasoning about each column.
This is a learning aid, not part of the app itself.
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")
    profile = understand_dataset(df)

    print("=" * 70)
    print("DETABETA -- ENGINE 1: DATASET UNDERSTANDING")
    print("=" * 70)

    print("\nDATASET OBSERVATIONS")
    print("-" * 70)
    for line in profile.observations:
        print(f"  - {line}")

    print("\nPER-COLUMN CLASSIFICATION")
    print("-" * 70)
    for col in profile.columns:
        print(f"\n  {col.name}  ->  {col.semantic_type.value.upper()}")
        print(f"    dtype={col.raw_dtype}  missing={col.missing_pct}%  "
              f"unique={col.n_unique}")
        for reason in col.reasoning:
            print(f"      why: {reason}")
        if col.stats:
            print(f"      stats: {col.stats}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
