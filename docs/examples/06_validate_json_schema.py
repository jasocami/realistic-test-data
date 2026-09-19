"""
Validate the JSON against its generated schema.

    pip install jsonschema
    python docs/examples/06_validate_json_schema.py

Both files come from the same Entity definitions, so this always passes --
which makes it a good fixture for testing YOUR validation layer. Break the
data deliberately at the end and watch the error you would get.
"""

import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPIC, ENTITY = "clinical", "patients"


def main() -> None:
    schema = json.loads(
        (REPO_ROOT / "schemas" / TOPIC / f"{ENTITY}.schema.json")
        .read_text(encoding="utf-8")
    )
    data = json.loads(
        (REPO_ROOT / "json" / TOPIC / f"{ENTITY}.json").read_text(encoding="utf-8")
    )

    jsonschema.validate(data, schema)
    print(f"✓ {len(data):,} {ENTITY} records validate against the schema")

    # What the schema actually declares.
    properties = schema["items"]["properties"]
    required = set(schema["items"]["required"])
    print(f"\n{len(properties)} properties, {len(required)} required:\n")
    for name, spec in list(properties.items())[:6]:
        nullable = "" if name in required else "  (nullable)"
        print(f"  {name:<16} {str(spec['type']):<22}{nullable}")

    # Now break it on purpose, to see the failure mode.
    broken = [dict(data[0])]
    broken[0]["date_of_birth"] = "the 3rd of March"
    try:
        jsonschema.validate(broken, schema)
    except jsonschema.ValidationError as error:
        print(f"\n✓ an invalid date is rejected as expected:")
        print(f"    {error.message[:100]}")


if __name__ == "__main__":
    main()
