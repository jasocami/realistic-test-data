"""
Stream a large table one record at a time.

    python docs/examples/04_stream_ndjson.py

The point of NDJSON: this script never holds more than one record in memory,
no matter how big the file gets. The equivalent .json file would have to be
parsed in full before you could touch the first record.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ATTENDANCE = REPO_ROOT / "json" / "education" / "attendance.ndjson"


def main() -> None:
    if not ATTENDANCE.exists():
        print(f"{ATTENDANCE.name} not found -- run `python build.py --topic education`")
        return

    counts: dict[str, int] = {}
    late_minutes = 0
    records = 0

    with ATTENDANCE.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)      # one record in memory at a time
            records += 1
            counts[record["status"]] = counts.get(record["status"], 0) + 1
            late_minutes += record["minutes_late"]

    print(f"streamed {records:,} attendance records "
          f"({ATTENDANCE.stat().st_size / 1024:,.0f} KB on disk)\n")

    for status, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"  {status:<10} {count:>6,}  {100 * count / records:>5.1f}%")

    print(f"\ntotal lateness recorded: {late_minutes:,} minutes")


if __name__ == "__main__":
    main()
