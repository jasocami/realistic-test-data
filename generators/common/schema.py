"""
The schema definition layer -- the single source of truth for this repository.
===============================================================================

WHAT IS THIS FILE?
------------------
Every table of data in this repository (patients, products, accounts...) is
described exactly once, as an `Entity` made of `Field` objects.

From that ONE description, the build produces SEVEN different things:

    1. csv/<topic>/<entity>.csv          the data as CSV
    2. json/<topic>/<entity>.json        the same data as JSON
    3. db/<topic>/<topic>.sqlite         the same data as a SQLite table
    4. schemas/<topic>/<entity>.schema.json   a JSON Schema for validation
    5. docs/topics/<topic>.md            a human-readable column dictionary
    6. csv/<topic>/README.md             the folder page GitHub shows
    7. tests/                            assertions that the files match

WHY DO IT THIS WAY?
-------------------
Because hand-written documentation goes stale. If the column list lives in a
Markdown file and the data lives somewhere else, they drift apart within
months and the docs start lying to people.

Here they cannot drift, because the documentation IS the schema. Change a
field description, rebuild, and every CSV header, JSON Schema, docs table and
folder README updates together.

THE DOCUMENTATION RULE
----------------------
`Field` refuses to be created without a real `description`. Not a warning --
an exception that stops the build. You physically cannot add an undocumented
column to this repository. See `_validate()` at the bottom of each class.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from .config import CDN_BASE

# ---------------------------------------------------------------------------
# The type system
# ---------------------------------------------------------------------------
# We deliberately keep this tiny. Eight types cover every column in every
# topic, and a small vocabulary is easier for a newcomer to hold in their head
# than a faithful mirror of SQL's ~40 types.

FIELD_TYPES = {
    "integer",    # whole number        -> 42
    "decimal",    # money / measurement -> 19.99  (always 2 decimal places)
    "string",     # short text          -> "Anna Whitfield"
    "text",       # long free text      -> a paragraph of clinical notes
    "date",       # ISO-8601 date       -> "2024-06-14"
    "datetime",   # ISO-8601 timestamp  -> "2024-06-14T09:30:00"
    "boolean",    # true / false        -> emitted as "true"/"false" in CSV
    "enum",       # one of a fixed list -> "O+", "A-", ...
}

# How each of our types is stored in SQLite.
#
# NOTE FOR JUNIORS -- why `decimal` maps to REAL:
# SQLite has no dedicated decimal type. Real production systems that handle
# money usually store integer *cents* to avoid floating-point rounding errors
# (0.1 + 0.2 != 0.3 in binary floating point). This repository does its money
# arithmetic in integer cents internally and only converts to a 2-decimal
# number when writing the file, so the totals always add up exactly. We then
# store the result as REAL because that is what a typical app would do.
# See docs/generators/money-and-rounding.md.
SQLITE_TYPES = {
    "integer": "INTEGER",
    "decimal": "REAL",
    "string": "TEXT",
    "text": "TEXT",
    "date": "TEXT",       # SQLite has no date type; ISO-8601 strings sort correctly
    "datetime": "TEXT",
    "boolean": "INTEGER",  # SQLite has no boolean either; 0 or 1
    "enum": "TEXT",
}

# How each of our types is expressed in JSON Schema, so that
# `schemas/<topic>/<entity>.schema.json` can validate the JSON files.
JSON_SCHEMA_TYPES = {
    "integer": {"type": "integer"},
    "decimal": {"type": "number"},
    "string": {"type": "string"},
    "text": {"type": "string"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
    "boolean": {"type": "boolean"},
    "enum": {"type": "string"},
}

# The minimum length of a field description, in characters.
# This exists to stop `description="the id"`, which is technically a
# description and practically useless to the person reading it.
MIN_DESCRIPTION_LENGTH = 40


class SchemaError(ValueError):
    """Raised when a schema definition breaks one of the repository's rules.

    This is deliberately a hard failure rather than a warning. A warning
    scrolls past unnoticed; an exception stops the build and gets fixed.
    """


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    """One column of one table.

    The only two required arguments are `name` and `type`, plus `description`
    -- which is required by rule rather than by signature, so that the error
    message can explain *why* when someone forgets it.

    Example::

        Field(
            "blood_type", "enum",
            description=(
                "ABO and Rh blood group. Distributed by real-world frequency, "
                "so O+ is roughly 37% of rows and AB- is under 1%."
            ),
            values=["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"],
            example="O+",
        )
    """

    name: str
    type: str
    description: str = ""

    # --- optional metadata -------------------------------------------------
    example: Any = None
    """A concrete sample value, shown in the generated docs. Juniors read one
    real value faster than three sentences of prose, so this is worth filling
    in even when the description is already clear."""

    nullable: bool = False
    """True if this column can be empty. Roughly 5% of genuinely optional
    columns in this repository ARE empty on purpose, because real data has
    gaps and code that consumes it has to survive them."""

    unique: bool = False
    primary_key: bool = False

    references: str | None = None
    """A foreign key, written as "entity.field" -- e.g. "patients.id".
    The build uses this to emit real FOREIGN KEY constraints in SQLite, to
    draw the arrows in the generated ER diagram, and to assert in the test
    suite that every single value actually resolves to a parent row."""

    values: list[Any] | None = None
    """The allowed values, for `enum` fields."""

    pattern: str | None = None
    """A regular expression the value always matches, e.g. r"^MRN-\\d{7}$".
    Emitted into the JSON Schema and checked by the tests."""

    unit: str | None = None
    """The unit of measurement, e.g. "EUR", "km", "mg/dL". Shown in the docs.
    Never guess at a column's unit -- say it here."""

    note: str | None = None
    """An extra paragraph for anything surprising about this column: a domain
    convention, a gotcha, why it exists at all. Rendered as a callout in the
    docs, below the table."""

    def __post_init__(self) -> None:
        self._validate()

    # -- validation ---------------------------------------------------------

    def _validate(self) -> None:
        if self.type not in FIELD_TYPES:
            raise SchemaError(
                f"Field {self.name!r} has unknown type {self.type!r}. "
                f"Valid types are: {', '.join(sorted(FIELD_TYPES))}."
            )

        # THE DOCUMENTATION GATE.
        if not self.description or not self.description.strip():
            raise SchemaError(
                f"Field {self.name!r} has no description.\n"
                f"\n"
                f"Every column in this repository must explain itself, because "
                f"the generated documentation is built from these descriptions "
                f"and somebody who has never seen this data has to understand "
                f"the column from it alone.\n"
                f"\n"
                f"Write what the column MEANS, not what it is called. "
                f'Not "the patient id" but "references patients.id -- the '
                f'person this appointment was booked for".'
            )

        if len(self.description.strip()) < MIN_DESCRIPTION_LENGTH:
            raise SchemaError(
                f"Field {self.name!r} has a description of only "
                f"{len(self.description.strip())} characters "
                f"({self.description.strip()!r}), but the minimum is "
                f"{MIN_DESCRIPTION_LENGTH}.\n"
                f"\n"
                f"Short descriptions are usually just the column name spelled "
                f"out with spaces, which tells the reader nothing they could "
                f"not already see. Explain the meaning, the units, the range, "
                f"or why the column exists."
            )

        if self.type == "enum" and not self.values:
            raise SchemaError(
                f"Field {self.name!r} is an enum but lists no `values=[...]`. "
                f"The allowed values go in the docs and the JSON Schema, so "
                f"consumers know what to expect without scanning the data."
            )

        if self.values and self.type != "enum":
            raise SchemaError(
                f"Field {self.name!r} has `values=` but its type is "
                f"{self.type!r}, not 'enum'."
            )

        if self.primary_key and self.nullable:
            raise SchemaError(
                f"Field {self.name!r} is a primary key and therefore cannot "
                f"be nullable."
            )

        if self.references and "." not in self.references:
            raise SchemaError(
                f"Field {self.name!r} has references={self.references!r}, "
                f'which must be written as "entity.field", e.g. "patients.id".'
            )

    # -- derived representations -------------------------------------------

    @property
    def referenced_entity(self) -> str | None:
        """"patients.id" -> "patients". None if this is not a foreign key."""
        return self.references.split(".")[0] if self.references else None

    @property
    def referenced_field(self) -> str | None:
        """"patients.id" -> "id". None if this is not a foreign key."""
        return self.references.split(".")[1] if self.references else None

    def sqlite_column(self) -> str:
        """Render this field as a line inside a CREATE TABLE statement."""
        parts = [f'"{self.name}"', SQLITE_TYPES[self.type]]
        if self.primary_key:
            parts.append("PRIMARY KEY")
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        if self.type == "enum" and self.values:
            # SQL escapes a single quote by doubling it, so the enum value
            # "Children's" has to become 'Children''s'. Forgetting this is
            # how you get `sqlite3.OperationalError: near "s": syntax error`.
            allowed = ", ".join(
                "'{}'".format(str(value).replace("'", "''")) for value in self.values
            )
            parts.append(f'CHECK ("{self.name}" IN ({allowed}))')
        return " ".join(parts)

    def json_schema(self) -> dict[str, Any]:
        """Render this field as a JSON Schema property."""
        spec: dict[str, Any] = dict(JSON_SCHEMA_TYPES[self.type])

        if self.type == "enum" and self.values:
            spec["enum"] = list(self.values)
        if self.pattern:
            spec["pattern"] = self.pattern

        # A nullable column is expressed as a union with "null".
        if self.nullable:
            declared = spec["type"]
            spec["type"] = [declared, "null"] if isinstance(declared, str) else [*declared, "null"]

        spec["description"] = self.description.strip()
        if self.example is not None:
            spec["examples"] = [self.example]
        return spec


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Entity:
    """One table of data, belonging to one topic.

    Example::

        Entity(
            name="patients",
            topic="clinical",
            grain="One row per person registered at any hospital in this dataset.",
            description="The anchor table of the clinical topic. ...",
            fields=[...],
        )
    """

    name: str
    topic: str
    grain: str
    """A single sentence beginning "One row per ...".

    This is the most useful sentence in any data dictionary and the one most
    often missing. Knowing that `transaction_items` is "one row per product
    scanned at a till" instantly tells you how to join it, how many rows to
    expect, and what a duplicate would mean."""

    description: str
    fields: list[Field]

    notes: list[str] = dataclass_field(default_factory=list)
    """Domain notes rendered under the column table -- realism decisions,
    known quirks, and anything a newcomer would otherwise have to work out by
    reading the data."""

    def __post_init__(self) -> None:
        self._validate()

    # -- validation ---------------------------------------------------------

    def _validate(self) -> None:
        if not self.fields:
            raise SchemaError(f"Entity {self.name!r} has no fields.")

        if not self.grain.strip().lower().startswith("one row per"):
            raise SchemaError(
                f'Entity {self.name!r} has grain={self.grain!r}, but grain '
                f'must begin with "One row per ...".\n'
                f"\n"
                f"The grain is the single most useful sentence in a data "
                f"dictionary: it tells the reader what a row *is*, which "
                f"determines how to join the table and what a duplicate means."
            )

        if len(self.description.strip()) < MIN_DESCRIPTION_LENGTH:
            raise SchemaError(
                f"Entity {self.name!r} needs a description of at least "
                f"{MIN_DESCRIPTION_LENGTH} characters explaining what it is "
                f"and how it relates to the rest of the topic."
            )

        names = [f.name for f in self.fields]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise SchemaError(
                f"Entity {self.name!r} has duplicate field names: "
                f"{', '.join(sorted(duplicates))}."
            )

        primary_keys = [f for f in self.fields if f.primary_key]
        if len(primary_keys) != 1:
            raise SchemaError(
                f"Entity {self.name!r} has {len(primary_keys)} primary keys; "
                f"exactly one is required. Every table in this repository "
                f"uses a single surrogate integer `id` column so that joins "
                f"are uniform and easy to explain."
            )

    # -- convenience --------------------------------------------------------

    @property
    def primary_key(self) -> Field:
        return next(f for f in self.fields if f.primary_key)

    @property
    def foreign_keys(self) -> list[Field]:
        return [f for f in self.fields if f.references]

    @property
    def column_names(self) -> list[str]:
        return [f.name for f in self.fields]

    def field(self, name: str) -> Field:
        try:
            return next(f for f in self.fields if f.name == name)
        except StopIteration:
            raise SchemaError(
                f"Entity {self.name!r} has no field {name!r}. "
                f"It has: {', '.join(self.column_names)}"
            ) from None

    # -- derived representations -------------------------------------------

    def create_table_sql(self) -> str:
        """Render the full CREATE TABLE statement, including foreign keys.

        The entity description is emitted as a SQL comment above the table so
        that someone who opens the .sqlite file in a GUI -- and therefore
        never reads our Markdown -- still gets the explanation.
        """
        lines = [f"-- {self.name}: {self.grain}", f'CREATE TABLE "{self.name}" (']

        body = [f"    {f.sqlite_column()}" for f in self.fields]
        for fk in self.foreign_keys:
            body.append(
                f'    FOREIGN KEY ("{fk.name}") '
                f'REFERENCES "{fk.referenced_entity}" ("{fk.referenced_field}")'
            )
        lines.append(",\n".join(body))
        lines.append(");")
        return "\n".join(lines)

    def index_sql(self) -> list[str]:
        """An index on every foreign key.

        Real schemas index their foreign keys, because joining on an
        unindexed column means a full table scan. Including them here means
        the SQLite files behave like a real database under a real query.
        """
        return [
            f'CREATE INDEX "idx_{self.name}_{fk.name}" '
            f'ON "{self.name}" ("{fk.name}");'
            for fk in self.foreign_keys
        ]

    def json_schema(self) -> dict[str, Any]:
        """Render a JSON Schema describing an ARRAY of these records.

        The JSON files in json/<topic>/ are arrays, so the schema validates
        the whole file rather than a single record.
        """
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            # Built from the repository config so it stays correct if the
            # repository is ever renamed. The previous hardcoded value was
            # missing the owner and the version tag, so it never resolved.
            "$id": f"{CDN_BASE}/schemas/{self.topic}/{self.name}.schema.json",
            "title": f"{self.topic}/{self.name}",
            "description": f"{self.grain} {self.description.strip()}",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {f.name: f.json_schema() for f in self.fields},
                "required": [f.name for f in self.fields if not f.nullable],
                "additionalProperties": False,
            },
        }


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Topic:
    """A group of related entities -- clinical, supermarket, finance, ...

    A topic maps to one folder inside every format directory:

        csv/clinical/      json/clinical/      db/clinical/
        pdf/clinical/      png/clinical/       jpeg/clinical/
    """

    name: str
    title: str
    """Human-readable name for headings, e.g. "Clinical / Healthcare"."""

    summary: str
    """One or two sentences for the folder README and the root index table."""

    description: str
    """The longer "what is this?" introduction for docs/topics/<name>.md.
    Written for somebody with no knowledge of the domain."""

    entities: list[Entity]

    def __post_init__(self) -> None:
        if not self.entities:
            raise SchemaError(f"Topic {self.name!r} has no entities.")

        for entity in self.entities:
            if entity.topic != self.name:
                raise SchemaError(
                    f"Entity {entity.name!r} says topic={entity.topic!r} but "
                    f"it is registered under topic {self.name!r}."
                )

        # Every foreign key must point at an entity that exists in this topic.
        # Catching this here means a typo fails immediately with a clear
        # message, instead of producing a SQLite file that won't open.
        known = {e.name for e in self.entities}
        for entity in self.entities:
            for fk in entity.foreign_keys:
                if fk.referenced_entity not in known:
                    raise SchemaError(
                        f"{entity.name}.{fk.name} references "
                        f"{fk.references!r}, but there is no entity named "
                        f"{fk.referenced_entity!r} in topic {self.name!r}. "
                        f"Known entities: {', '.join(sorted(known))}."
                    )

    def entity(self, name: str) -> Entity:
        try:
            return next(e for e in self.entities if e.name == name)
        except StopIteration:
            raise SchemaError(
                f"Topic {self.name!r} has no entity {name!r}. It has: "
                f"{', '.join(e.name for e in self.entities)}"
            ) from None

    def build_order(self) -> list[Entity]:
        """Return the entities ordered so parents always come before children.

        This is a topological sort over the foreign keys. We need it because
        SQLite will reject an INSERT that references a row which does not
        exist yet, so `patients` has to be written before `appointments`.

        A cycle (A references B references A) is a schema design error and
        raises, rather than looping forever.
        """
        ordered: list[Entity] = []
        placed: set[str] = set()
        remaining = list(self.entities)

        while remaining:
            progressed = False
            for entity in list(remaining):
                parents = {
                    fk.referenced_entity
                    for fk in entity.foreign_keys
                    # A self-reference (categories.parent_id -> categories.id)
                    # does not block insertion; we just insert parents first
                    # within the table itself.
                    if fk.referenced_entity != entity.name
                }
                if parents <= placed:
                    ordered.append(entity)
                    placed.add(entity.name)
                    remaining.remove(entity)
                    progressed = True

            if not progressed:
                stuck = ", ".join(e.name for e in remaining)
                raise SchemaError(
                    f"Circular foreign keys in topic {self.name!r} among: "
                    f"{stuck}. Tables must form a directed acyclic graph so "
                    f"they can be inserted parents-first."
                )

        return ordered
