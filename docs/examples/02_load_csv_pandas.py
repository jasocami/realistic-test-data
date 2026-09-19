"""
Load a CSV with pandas, avoiding the two traps.

    pip install pandas
    python docs/examples/02_load_csv_pandas.py
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PATIENTS = REPO_ROOT / "csv" / "clinical" / "patients.csv"


def main() -> None:
    # TRAP 1: postal codes are strings, not numbers.
    #   Without dtype=str, pandas reads "08011" as the integer 8011 and the
    #   leading zero is gone. Every Spanish province from 01 to 09 breaks.
    #
    # TRAP 2: empty strings become NaN.
    #   keep_default_na=False keeps them as "", which matters if you want to
    #   distinguish "no email recorded" from "the float NaN".
    patients = pd.read_csv(
        PATIENTS,
        dtype={"postal_code": str},
        keep_default_na=False,
        parse_dates=["date_of_birth", "registered_at"],
    )

    print(f"{len(patients):,} patients, {len(patients.columns)} columns\n")
    print(patients[["mrn", "full_name", "city", "postal_code"]].head().to_string(index=False))

    # Province codes really are the first two digits of the postal code.
    derived = patients["postal_code"].str[:2]
    print(f"\ndistinct province codes seen: {derived.nunique()}")

    print("\npatients per province (top 5):")
    print(patients["province"].value_counts().head().to_string())

    # Ages, from the parsed dates.
    as_of = pd.Timestamp("2025-06-30")
    ages = ((as_of - patients["date_of_birth"]).dt.days / 365.25).astype(int)
    print(f"\nage: min {ages.min()}, median {int(ages.median())}, max {ages.max()}")


if __name__ == "__main__":
    main()
