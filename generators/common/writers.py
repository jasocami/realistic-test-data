"""
Writing one set of records out to every format.
===============================================================================

WHAT IS THIS FILE?
------------------
A topic generator produces plain Python dictionaries -- one per row. This file
turns those dictionaries into the actual files people download:

    write_csv()      ->  csv/<topic>/<entity>.csv
    write_json()     ->  json/<topic>/<entity>.json
    write_ndjson()   ->  json/<topic>/<entity>.ndjson
    write_sqlite()   ->  db/<topic>/<topic>.sqlite
    write_schema()   ->  schemas/<topic>/<entity>.schema.json

THE GUARANTEE THIS FILE EXISTS TO PROVIDE
-----------------------------------------
All formats are written from the SAME list of dictionaries, in the same
order. That is what makes this repository's central promise true:

    csv/clinical/patients.csv
    json/clinical/patients.json
    the `patients` table in db/clinical/clinical.sqlite

...all contain exactly the same 1,000 records, in the same order, with the
same values. You can diff them. The test suite does.

FORMATTING RULES
----------------
Every format has its own idea of how to write "nothing", "true" and "19.99".
Those decisions are made once, here, rather than scattered through the topic
generators:

    Python value   CSV            JSON        SQLite
    ------------   ------------   ---------   ----------
    None           (empty)        null        NULL
    True           true           true        1
    Decimal 19.9   19.90          19.9        19.9
    date(2024,1,1) 2024-01-01     "2024-..."  "2024-01-01"
"""

from __future__ import annotations

import csv
import gzip
import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .schema import Entity

# The repository root -- three levels up from generators/common/writers.py.
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------

def _format_for_csv(value: Any, field_type: str) -> str:
    """Render one Python value as it should appear in a CSV cell.

    CSV has no types -- everything is text -- so every decision about how a
    value *looks* is made here.
    """
    if value is None:
        # An empty cell. Note this is genuinely ambiguous in CSV: an empty
        # string and a missing value look identical. That ambiguity is real
        # and worth experiencing, which is part of why we don't quote NULLs
        # differently. docs/formats/csv.md explains it.
        return ""

    if field_type == "boolean":
        # Lowercase "true"/"false" matches JSON, so a naive CSV->JSON
        # conversion does the right thing.
        return "true" if value else "false"

    if field_type == "decimal":
        # Always exactly two decimal places, so money columns line up and
        # string comparison between formats is meaningful. 19.9 -> "19.90".
        return f"{Decimal(str(value)):.2f}"

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return str(value)


def _format_for_json(value: Any, field_type: str) -> Any:
    """Render one Python value as a JSON-native type."""
    if value is None:
        return None
    if field_type == "boolean":
        return bool(value)
    if field_type == "decimal":
        # JSON numbers, not strings -- so `data[0]["price"] * 2` works in
        # every language without parsing. We round to 2dp for consistency
        # with the CSV, accepting that JSON will drop a trailing zero
        # (19.90 becomes 19.9). The values are equal; only the rendering
        # differs, and the test suite compares them numerically.
        return float(round(Decimal(str(value)), 2))
    if field_type == "integer":
        return int(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _format_for_sqlite(value: Any, field_type: str) -> Any:
    """Render one Python value as something sqlite3 will accept."""
    if value is None:
        return None
    if field_type == "boolean":
        # SQLite has no boolean type. 1 and 0 are the universal convention.
        return 1 if value else 0
    if field_type == "decimal":
        return float(round(Decimal(str(value)), 2))
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def write_csv(entity: Entity, rows: list[dict[str, Any]], root: Path = REPO_ROOT) -> Path:
    """Write ``csv/<topic>/<entity>.csv``.

    Conventions, all chosen to be the least surprising option:

    * UTF-8, no byte-order mark
    * comma separated, RFC 4180 quoting (only quote when necessary)
    * "\\n" line endings, including on Windows
    * one header row of column names
    """
    path = root / "csv" / entity.topic / f"{entity.name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    types = {f.name: f.type for f in entity.fields}

    # newline="" is required by the csv module so it can control line endings
    # itself; without it Windows would write "\r\r\n".
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(entity.column_names)
        for row in rows:
            writer.writerow(
                _format_for_csv(row.get(name), types[name])
                for name in entity.column_names
            )

    return path


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def write_json(entity: Entity, rows: list[dict[str, Any]], root: Path = REPO_ROOT) -> Path:
    """Write ``json/<topic>/<entity>.json`` as a pretty-printed array.

    Indented with 2 spaces and left readable rather than minified, because
    these files are meant to be opened and looked at. The gzipped transfer
    size difference is negligible and GitHub renders them nicely.
    """
    path = root / "json" / entity.topic / f"{entity.name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    types = {f.name: f.type for f in entity.fields}
    records = [
        {name: _format_for_json(row.get(name), types[name]) for name in entity.column_names}
        for row in rows
    ]

    with path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)
        handle.write("\n")  # POSIX: text files end with a newline

    return path


def write_ndjson(entity: Entity, rows: list[dict[str, Any]], root: Path = REPO_ROOT) -> Path:
    """Write ``json/<topic>/<entity>.ndjson`` -- one JSON object per line.

    WHAT IS NDJSON? "Newline-delimited JSON". Instead of one big array, each
    line is a complete, independent JSON object.

    WHY IT EXISTS: a 50,000-record JSON array has to be fully downloaded and
    fully parsed before you can look at the first record. NDJSON can be
    streamed -- read a line, parse it, handle it, discard it -- with constant
    memory. It is what log pipelines, BigQuery, and most "export" endpoints
    actually use, so it is worth having something to test against.
    """
    path = root / "json" / entity.topic / f"{entity.name}.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)

    types = {f.name: f.type for f in entity.fields}

    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = {
                name: _format_for_json(row.get(name), types[name])
                for name in entity.column_names
            }
            # separators without spaces: NDJSON lines are for machines.
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    return path


def write_schema(entity: Entity, root: Path = REPO_ROOT) -> Path:
    """Write ``schemas/<topic>/<entity>.schema.json``.

    This is generated straight from the Entity definition, so it can never
    disagree with the data. The test suite validates every JSON file against
    its schema, which means a generator bug that produces a wrong type or a
    missing field fails the build.
    """
    path = root / "schemas" / entity.topic / f"{entity.name}.schema.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(entity.json_schema(), handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    return path


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def write_sqlite(
    topic_name: str,
    tables: Iterable[tuple[Entity, list[dict[str, Any]]]],
    root: Path = REPO_ROOT,
) -> Path:
    """Write ``db/<topic>/<topic>.sqlite`` containing every entity as a table.

    Unlike the other writers this takes the WHOLE topic at once, because a
    relational database is not a pile of independent tables -- the foreign
    keys have to resolve, so the tables must be created and filled in
    dependency order (patients before appointments).

    What you get:

    * one table per entity, with real FOREIGN KEY constraints
    * an index on every foreign key column
    * ``PRAGMA foreign_keys = ON`` enforced during the load, so a broken
      reference fails the build instead of silently shipping

    NOTE FOR JUNIORS: SQLite does NOT enforce foreign keys by default -- it
    accepts the constraint syntax and then ignores it unless you switch the
    pragma on. This surprises almost everyone the first time. It is off by
    default for backwards compatibility with very old database files. You
    have to run ``PRAGMA foreign_keys = ON;`` in *every connection*, which is
    exactly what docs/formats/sqlite.md tells people to do.
    """
    tables = list(tables)
    path = root / "db" / topic_name / f"{topic_name}.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)

    # Always rebuild from scratch; otherwise a rename would leave the old
    # table behind and the file would stop being reproducible.
    path.unlink(missing_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON;")

        for entity, _ in tables:
            # sqlite3.execute() takes exactly one statement, so strip the
            # leading "-- table: grain" comment line that create_table_sql()
            # adds for the benefit of the .sql dump and GUI users.
            statement = "\n".join(
                line
                for line in entity.create_table_sql().splitlines()
                if not line.lstrip().startswith("--")
            )
            connection.execute(statement)
            for index_statement in entity.index_sql():
                connection.execute(index_statement)

        for entity, rows in tables:
            types = {f.name: f.type for f in entity.fields}
            columns = ", ".join(f'"{name}"' for name in entity.column_names)
            placeholders = ", ".join("?" for _ in entity.column_names)
            connection.executemany(
                f'INSERT INTO "{entity.name}" ({columns}) VALUES ({placeholders});',
                [
                    tuple(
                        _format_for_sqlite(row.get(name), types[name])
                        for name in entity.column_names
                    )
                    for row in rows
                ],
            )

        # Ask SQLite to confirm no foreign key was left dangling. If the
        # generators produced an orphan row, we find out here rather than a
        # user finding out later.
        violations = connection.execute("PRAGMA foreign_key_check;").fetchall()
        if violations:
            raise RuntimeError(
                f"Foreign key violations in {topic_name}.sqlite: {violations[:5]}"
            )

        connection.commit()

        # VACUUM rewrites the file compactly and, importantly for us,
        # deterministically -- so rebuilding produces an identical file.
        connection.execute("VACUUM;")
        connection.commit()
    finally:
        connection.close()

    return path


def write_schema_sql(
    topic_name: str,
    tables: Iterable[tuple[Entity, list[dict[str, Any]]]],
    root: Path = REPO_ROOT,
) -> Path:
    """Write ``db/<topic>/schema.sql`` -- the table structure, no data.

    A few kilobytes of readable DDL. This is the file to open when you want
    to know what the tables look like, and the one to paste into a database
    when you want the structure to load your own data into. It is kept
    separate from the data dump precisely so it stays small enough to read.
    """
    tables = list(tables)
    path = root / "db" / topic_name / "schema.sql"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"-- {topic_name}/schema.sql",
        f"-- Table structure for the '{topic_name}' topic. No data -- see",
        f"-- {topic_name}.sql.gz for the rows, or {topic_name}.sqlite for a",
        "-- database you can query immediately.",
        "--",
        "-- SYNTHETIC DATA -- every record is invented. See README.md.",
        "",
        "PRAGMA foreign_keys = ON;",
        "",
    ]
    for entity, _ in tables:
        lines.append(entity.create_table_sql())
        lines.extend(entity.index_sql())
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_sql_dump(
    topic_name: str,
    tables: Iterable[tuple[Entity, list[dict[str, Any]]]],
    root: Path = REPO_ROOT,
) -> Path:
    """Write ``db/<topic>/<topic>.sql.gz`` -- structure and data, gzipped.

    WHY BOTH .sqlite AND .sql.gz? The .sqlite file is ready to query
    immediately, but only by SQLite. The SQL dump is portable text you can
    load into PostgreSQL or MySQL instead.

    WHY GZIPPED? Because plain SQL is enormously repetitive -- the same
    INSERT INTO "lab_results" (...) VALUES prefix on every one of 8,000 rows
    -- and compresses about six to one. Uncompressed it was the single
    largest file in the repository, duplicating data that the .sqlite file
    already holds in a fraction of the space. Nobody reads a five-megabyte
    dump in a diff, so there is nothing to lose by compressing it.

    To load it::

        gunzip -c db/clinical/clinical.sql.gz | sqlite3 mycopy.sqlite
        gunzip -c db/clinical/clinical.sql.gz | psql mydatabase
    """
    tables = list(tables)
    path = root / "db" / topic_name / f"{topic_name}.sql.gz"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"-- {topic_name}.sql",
        "-- Schema and data for the '%s' topic of the realistic-test-data repository." % topic_name,
        "-- SYNTHETIC DATA -- every record is invented. See README.md.",
        "",
        "PRAGMA foreign_keys = ON;",
        "",
    ]

    for entity, _ in tables:
        lines.append(entity.create_table_sql())
        lines.extend(entity.index_sql())
        lines.append("")

    for entity, rows in tables:
        types = {f.name: f.type for f in entity.fields}
        columns = ", ".join(f'"{name}"' for name in entity.column_names)
        lines.append(f"-- {len(rows):,} rows")
        for row in rows:
            values = []
            for name in entity.column_names:
                value = _format_for_sqlite(row.get(name), types[name])
                if value is None:
                    values.append("NULL")
                elif isinstance(value, (int, float)):
                    values.append(str(value))
                else:
                    escaped = str(value).replace("'", "''")
                    values.append(f"'{escaped}'")
            lines.append(
                f'INSERT INTO "{entity.name}" ({columns}) VALUES ({", ".join(values)});'
            )
        lines.append("")

    # mtime=0 so the gzip header carries no timestamp. Without this the file
    # would differ on every build and break reproducibility -- a classic
    # gotcha when compressing generated artifacts.
    with gzip.GzipFile(path, "wb", compresslevel=9, mtime=0) as handle:
        handle.write("\n".join(lines).encode("utf-8"))

    return path
