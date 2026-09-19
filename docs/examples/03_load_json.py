"""
Load the JSON, and see what it gives you that the CSV cannot.

    python docs/examples/03_load_json.py
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    path = REPO_ROOT / "json" / "clinical" / "patients.json"
    patients = json.loads(path.read_text(encoding="utf-8"))

    print(f"{len(patients):,} patients\n")

    first = patients[0]
    print("first record:")
    for key, value in list(first.items())[:6]:
        print(f"  {key:<16} {value!r:<32} {type(value).__name__}")

    # THE DIFFERENCE FROM CSV: a real null.
    #
    # In the CSV an absent email is "" -- indistinguishable from an email
    # that is genuinely an empty string. Here it is None, and you can tell.
    no_email = [p for p in patients if p["email"] is None]
    print(f"\n{len(no_email)} patients have email == None (not \"\")")

    # Numbers are numbers, so arithmetic works without parsing.
    policies = json.loads(
        (REPO_ROOT / "json" / "clinical" / "insurance_policies.json")
        .read_text(encoding="utf-8")
    )
    total = sum(p["annual_premium"] for p in policies)
    print(f"\ntotal annual premiums: EUR {total:,.2f} across {len(policies)} policies")
    print(f"mean premium:          EUR {total / len(policies):,.2f}")


if __name__ == "__main__":
    main()
