"""
Demo for Engine 9 (Report) -- the capstone of the whole pipeline.

Run it:
    cd backend && source ../.venv/bin/activate && python demo_engine9.py

This runs Engines 1-8 on the passengers dataset and prints the single, ordered
"Data Story" that Engine 9 composes from all of their outputs.
"""

from __future__ import annotations

import pandas as pd

from engines.report import generate_report


def _rule(char: str = "=") -> str:
    return char * 74


def main() -> None:
    df = pd.read_csv("sample_data/passengers.csv")

    story = generate_report(df, target="survived", dataset_name="Passengers")

    print(_rule())
    print(story.title.upper())
    print(_rule())

    print("\nEXECUTIVE SUMMARY")
    print("-" * 74)
    for line in story.executive_summary:
        print(f"  {line}")

    print("\nHEADLINE VERDICTS")
    print("-" * 74)
    print(f"  Trust level      : {story.trust_level}")
    print(f"  Headline finding : {story.headline_finding}")
    print(f"  Model verdict    : {story.model_verdict or 'n/a'}")

    print("\n" + _rule())
    print("THE FULL STORY")
    print(_rule())
    for i, section in enumerate(story.sections, start=1):
        print(f"\n[{i}] {section.title}")
        print(f"    >> {section.headline}")
        for para in section.body:
            print(f"    {para}")
        for point in section.key_points:
            print(f"      - {point}")

    if story.caveats:
        print("\n" + _rule())
        print("CAVEATS (read before trusting the above)")
        print(_rule())
        for c in story.caveats:
            print(f"  ! {c}")

    print("\n" + _rule())
    print("RECOMMENDED NEXT STEPS")
    print(_rule())
    for i, step in enumerate(story.next_steps, start=1):
        print(f"  {i}. {step}")
    print()


if __name__ == "__main__":
    main()
