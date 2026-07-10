"""
Run Engine 3 (Investigation) on the sample passengers dataset and print the
findings the way the Investigation screen eventually will.

Usage:
    cd backend && source ../.venv/bin/activate && python demo_engine3.py
"""

from __future__ import annotations

import pandas as pd

from engines.dataset_understanding import understand_dataset
from engines.investigation import investigate


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")

    # Engine 1 first (Engine 3 needs to know what each column MEANS)...
    profile = understand_dataset(df)
    # ...then investigate, focusing on "survived" as the target of interest.
    report = investigate(df, profile=profile, target="survived")

    print("=" * 70)
    print("ENGINE 3: INVESTIGATION  --  'What interesting things exist?'")
    print("=" * 70)
    print(f"\nTarget under investigation: {report.target}")

    print("\nSUMMARY")
    print("-" * 70)
    for line in report.summary:
        print(f"  {line}")

    print(f"\nALL FINDINGS ({report.n_findings}), strongest first")
    print("-" * 70)
    for i, f in enumerate(report.findings, start=1):
        print(f"\n[{i}] {f.title}")
        print(f"    type      : {f.finding_type.value}")
        print(f"    strength  : {f.strength.value}  (score {f.score})")
        if f.direction:
            print(f"    direction : {f.direction}")
        print(f"    columns   : {', '.join(f.columns)}")
        print(f"    evidence  : {f.evidence}")
        for reason in f.reasoning:
            print(f"    why       : {reason}")
        print(f"    next step : {f.suggested_next_step}")
        print(f"    confirm?  : {'needs Engine 4 significance test' if f.needs_significance_test else 'factual, no test needed'}")


if __name__ == "__main__":
    main()
