"""
Demo runner for Engine 2 (Data Health).

Run it to SEE the engine reason about a deliberately messy dataset:

    cd backend
    source ../.venv/bin/activate
    python demo_engine2.py

'messy_customers.csv' was crafted to trigger many health issues at once:
    - missing incomes and ages
    - a duplicate final row
    - an extreme income outlier (999999)
    - inconsistent country spellings ("USA" / "usa" / " USA ", "UK" / "uk")
    - a heavily imbalanced 'subscribed' flag
so you can watch Engine 2 catch and explain each one.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engines.data_health import assess_health

DATA = Path(__file__).parent / "sample_data" / "messy_customers.csv"


def main() -> None:
    df = pd.read_csv(DATA)

    report = assess_health(df)

    print("=" * 70)
    print("ENGINE 2: DATA HEALTH REPORT")
    print("=" * 70)

    print("\nSUMMARY")
    print("-" * 70)
    for line in report.summary:
        print(f"  - {line}")

    print(f"\nISSUES ({len(report.issues)} found, most urgent first)")
    print("-" * 70)
    for i, issue in enumerate(report.issues, start=1):
        target = f" [column: {issue.column}]" if issue.column else " [dataset]"
        print(f"\n{i}. ({issue.severity.value.upper()}) {issue.title}{target}")
        print(f"   Category      : {issue.category.value}")
        print(f"   Recommendation: {issue.recommendation}")
        print("   Why:")
        for reason in issue.reasoning:
            print(f"     * {reason}")
        if issue.evidence:
            print(f"   Evidence      : {issue.evidence}")


if __name__ == "__main__":
    main()
