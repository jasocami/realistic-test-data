"""
Verify that the identifiers in this repository are structurally valid.

    python docs/examples/07_verify_check_digits.py

Every IBAN, VIN, DNI and barcode here carries a real check digit. This
script recomputes them all, using the repository's own implementations --
which are documented in generators/common/identifiers.py if you want to see
how each algorithm works.
"""

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from generators.common.identifiers import (  # noqa: E402
    dni_is_valid,
    ean13_is_valid,
    iban_is_valid,
    licence_plate_is_valid,
    luhn_is_valid,
    vin_is_valid,
)


def check(label: str, values: list[str], validator) -> None:
    bad = [value for value in values if not validator(value)]
    status = "✓" if not bad else "✗"
    print(f"  {status} {label:<34} {len(values):>6,} checked, {len(bad)} invalid")
    if bad:
        print(f"      first few: {bad[:3]}")


def rows(database: str, query: str) -> list[str]:
    connection = sqlite3.connect(REPO_ROOT / "db" / database / f"{database}.sqlite")
    try:
        return [row[0] for row in connection.execute(query)]
    finally:
        connection.close()


def main() -> None:
    print("Recomputing every check digit in the repository:\n")

    check("Spanish IBANs (mod-97)",
          rows("finance", "SELECT iban FROM accounts"), iban_is_valid)

    check("DNI check letters (mod-23)",
          rows("finance", "SELECT national_id FROM customers"), dni_is_valid)

    check("EAN-13 barcodes",
          rows("supermarket", "SELECT ean13 FROM products"), ean13_is_valid)

    check("VINs (ISO 3779)",
          rows("automobile", "SELECT vin FROM vehicles"), vin_is_valid)

    check("Spanish registration plates",
          rows("automobile", "SELECT plate FROM vehicles"), licence_plate_is_valid)

    # Card numbers are masked in the data, so reconstruct one to show Luhn.
    print()
    print("  Luhn, on a published test card number:")
    for number in ["4111111111111111", "4111111111111112"]:
        print(f"    {number}  {'valid' if luhn_is_valid(number) else 'INVALID'}")


if __name__ == "__main__":
    main()
