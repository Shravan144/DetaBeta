"""
Demo for Engine 4 (Statistics).

Run it:
    cd backend && source ../.venv/bin/activate && python demo_engine4.py

It chains all four engines on the passengers dataset:
    Engine 1 -> what kind of data is this?
    Engine 3 -> what leads exist?
    Engine 4 -> which of those leads survive a real significance test?
"""

from pathlib import Path

import pandas as pd

from engines.statistics import analyze_significance
from engines.statistics.types import Significance

DATA = Path(__file__).parent / "sample_data" / "passengers.csv"


def main() -> None:
    df = pd.read_csv(DATA)
    print(f"Loaded {DATA.name}: {df.shape[0]} rows x {df.shape[1]} columns\n")

    # We tell Engine 4 the target so it also runs target-focused tests.
    report = analyze_significance(df, target="survived")

    print("=" * 70)
    print("ENGINE 4: STATISTICS -- Evidence Report")
    print("=" * 70)
    print(f"\nTests run: {report.n_tests}   alpha: {report.alpha}", end="")
    if report.bonferroni_alpha:
        print(f"   Bonferroni alpha: {report.bonferroni_alpha:.4f}")
    else:
        print()

    print("\nSUMMARY")
    print("-" * 70)
    for line in report.summary:
        print(f"  - {line}")

    print("\nALL TESTS (most significant first)")
    print("-" * 70)
    ordered = sorted(report.tests, key=lambda t: (t.p_value if t.p_value == t.p_value else 1.0))
    for t in ordered:
        flag = {
            Significance.SIGNIFICANT: "[SIGNIFICANT]",
            Significance.NOT_SIGNIFICANT: "[not significant]",
            Significance.INCONCLUSIVE: "[inconclusive]",
        }[t.significance]
        p_str = "n/a" if t.p_value != t.p_value else f"{t.p_value:.4g}"
        eff = (
            f"{t.effect_metric}={t.effect_value} ({t.effect_size.value})"
            if t.effect_value is not None
            else "no effect size"
        )
        print(f"\n{flag} {t.title}   [{t.test_kind.value}]")
        print(f"    p-value: {p_str}    {eff}")
        for line in t.interpretation:
            print(f"    * {line}")
        for c in t.caveats:
            print(f"    ! {c}")


if __name__ == "__main__":
    main()
