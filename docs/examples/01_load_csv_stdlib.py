"""
Load a CSV with nothing but the Python standard library.

    python docs/examples/01_load_csv_stdlib.py

No pip install required. If you only need to read a table once, this is all
it takes -- pandas is convenient but not necessary.
"""

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATIENTS = REPO_ROOT / "csv" / "clinical" / "patients.csv"


def main() -> None:
    # newline="" is required by the csv module so it can handle quoted
    # fields that contain line breaks. Without it those rows split in two.
    with PATIENTS.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    print(f"{len(rows):,} patients\n")

    for row in rows[:5]:
        # Every value from csv is a STRING -- there are no types in CSV.
        print(f"  {row['mrn']}  {row['full_name']:<28} "
              f"{row['city']:<12} {row['postal_code']}")

    # Empty fields come back as "", not None. CSV cannot tell you whether a
    # blank means "empty string" or "missing" -- the JSON files can.
    missing_email = sum(1 for row in rows if row["email"] == "")
    print(f"\n{missing_email} of {len(rows)} patients have no email on file "
          f"({100 * missing_email / len(rows):.0f}%)")

    # Counting by a column, without pandas.
    from collections import Counter
    print("\nblood types:")
    for blood_type, count in Counter(r["blood_type"] for r in rows).most_common():
        print(f"  {blood_type:<4} {count:>4}  {100 * count / len(rows):>5.1f}%")


if __name__ == "__main__":
    main()
