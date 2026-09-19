"""
Documentation completeness gates.
===============================================================================

WHAT IS THIS FILE?
------------------
These tests make good documentation a build requirement rather than a good
intention.

The repository's promise is that somebody who has never seen this data can
understand any column from its description alone. That promise decays the
moment one undocumented column slips in, because the reader learns the
documentation is not reliable and stops trusting all of it.

So instead of hoping, we assert. A column with no description, or a
description that is really just the column name spelled out, fails CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import ALL_TOPICS

#: Words that, on their own, do not explain anything. A description made
#: only of these plus the column name is not a description.
FILLER_ONLY = re.compile(
    r"^(the|a|an|this|is|of|for|to|in|and|or|its|it|s|id|name|value|"
    r"date|time|number|code|type|status|column|field)\W*$",
    re.IGNORECASE,
)


@pytest.mark.parametrize(
    "entity",
    [entity for topic in ALL_TOPICS for entity in topic.entities],
    ids=lambda entity: f"{entity.topic}.{entity.name}",
)
def test_every_column_has_a_real_description(entity):
    """No column may ship without an explanation a newcomer could use."""
    for field in entity.fields:
        description = field.description.strip()

        assert description, (
            f"{entity.name}.{field.name} has no description. Every column in "
            f"this repository must explain itself -- the generated docs are "
            f"built from these strings."
        )
        assert len(description) >= 40, (
            f"{entity.name}.{field.name} has a {len(description)}-character "
            f"description: {description!r}. Explain what the column MEANS, "
            f"its units, or its range -- not just its name in longer form."
        )

        # Catch the "description is just the column name" failure mode:
        # `full_name` -> "The full name." tells the reader nothing.
        words = re.sub(r"[^a-z ]", " ", description.lower()).split()
        name_words = set(field.name.lower().split("_"))
        informative = [
            word for word in words
            if word not in name_words and not FILLER_ONLY.match(word)
        ]
        assert len(informative) >= 5, (
            f"{entity.name}.{field.name}: the description restates the column "
            f"name without adding information ({description!r}). Say what it "
            f"means, where it comes from, or what a consumer should expect."
        )


@pytest.mark.parametrize("entity",
    [entity for topic in ALL_TOPICS for entity in topic.entities],
    ids=lambda entity: f"{entity.topic}.{entity.name}")
def test_every_table_declares_its_grain(entity):
    """Every table must say what one row represents.

    The grain is the single most useful line in a data dictionary: it tells
    you how to join the table and what a duplicate would mean.
    """
    assert entity.grain.strip().lower().startswith("one row per"), (
        f"{entity.name}.grain must begin 'One row per ...', got "
        f"{entity.grain!r}"
    )
    assert len(entity.grain.strip()) >= 25, (
        f"{entity.name}.grain is too short to be useful: {entity.grain!r}"
    )


@pytest.mark.parametrize("entity",
    [entity for topic in ALL_TOPICS for entity in topic.entities],
    ids=lambda entity: f"{entity.topic}.{entity.name}")
def test_every_column_with_a_unit_says_so(entity):
    """Columns holding a measurement must declare their unit.

    A column called `premium` holding `2480.00` is ambiguous -- dollars?
    cents? per month? per year? Guessing wrong is a real bug, so the unit is
    required rather than optional for money and measurements.
    """
    money_or_measure = re.compile(
        r"(price|premium|cost|amount|balance|total|salary|fee|"
        r"mileage|distance|weight|height|duration|capacity)",
        re.IGNORECASE,
    )
    for field in entity.fields:
        if field.type in ("decimal", "integer") and money_or_measure.search(field.name):
            assert field.unit, (
                f"{entity.name}.{field.name} looks like a measurement but "
                f"declares no `unit=`. Add one (e.g. unit=\"USD\", unit=\"km\") "
                f"so nobody has to guess."
            )


@pytest.mark.parametrize("entity",
    [entity for topic in ALL_TOPICS for entity in topic.entities],
    ids=lambda entity: f"{entity.topic}.{entity.name}")
def test_every_column_has_an_example(entity):
    """A concrete sample value is faster to read than any description."""
    missing = [field.name for field in entity.fields if field.example is None]
    assert not missing, (
        f"{entity.name}: no `example=` on {', '.join(missing)}. One real "
        f"value communicates the shape of a column faster than a paragraph."
    )


def test_generated_topic_pages_exist_and_look_complete(repo_root: Path):
    """docs/topics/<topic>.md must exist and mention every table and column."""
    for topic in ALL_TOPICS:
        page = repo_root / "docs" / "topics" / f"{topic.name}.md"
        if not page.exists():
            pytest.skip(f"{page} not generated yet -- run `python build.py`")

        text = page.read_text(encoding="utf-8")

        assert "SYNTHETIC DATA" in text, (
            f"{page} is missing the synthetic-data banner. Every page that "
            f"describes this data has to say it is not real."
        )
        assert "```mermaid" in text, f"{page} has no ER diagram."

        for entity in topic.entities:
            assert f"`{entity.name}`" in text, (
                f"{page} does not document the {entity.name} table."
            )
            for field in entity.fields:
                assert f"`{field.name}`" in text, (
                    f"{page} does not document {entity.name}.{field.name}."
                )


def test_generated_folder_readmes_exist(repo_root: Path):
    """Every populated data folder must carry the README GitHub renders."""
    for format_dir in ("csv", "json", "db"):
        for topic in ALL_TOPICS:
            folder = repo_root / format_dir / topic.name
            data_files = [
                path for path in folder.glob("*")
                if path.is_file() and path.name != "README.md"
            ] if folder.is_dir() else []

            if not data_files:
                continue

            readme = folder / "README.md"
            assert readme.exists(), (
                f"{folder} holds {len(data_files)} files but no README.md. "
                f"Somebody following a deep link here would see a bare file "
                f"listing with no explanation."
            )
            text = readme.read_text(encoding="utf-8")
            assert "SYNTHETIC DATA" in text
            for path in data_files:
                assert f"`{path.name}`" in text, (
                    f"{readme} does not list {path.name}."
                )


# ---------------------------------------------------------------------------
# Entity-relationship diagrams
# ---------------------------------------------------------------------------

def test_erd_image_exists_and_is_a_real_png(repo_root: Path):
    """Every topic must ship a rendered ERD.

    Skipped rather than failed when Graphviz is absent, because it is an
    optional system dependency -- see generators/renderers/erd.py.
    """
    from generators.renderers.erd import graphviz_available

    for topic in ALL_TOPICS:
        image = repo_root / "png" / topic.name / "erd.png"
        if not image.exists():
            if not graphviz_available():
                pytest.skip("Graphviz 'dot' is not installed")
            pytest.fail(f"{image} is missing -- run `python build.py`")

        # A PNG always begins with this eight-byte signature. Checking it
        # catches a truncated or half-written file, which a size check alone
        # would not.
        assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", (
            f"{image} is not a valid PNG"
        )
        assert image.stat().st_size > 20_000, f"{image} looks suspiciously small"


def test_erd_covers_every_table_and_relationship(repo_root: Path):
    """The DOT source must mention every table and every foreign key.

    The image is generated from the schema, so this is really a check that
    nothing is silently dropped during rendering -- for instance a table
    that ends up with no node because of a naming mistake.
    """
    for topic in ALL_TOPICS:
        dot_path = repo_root / "png" / topic.name / "erd.dot"
        if not dot_path.exists():
            pytest.skip(f"{dot_path} not generated")

        source = dot_path.read_text(encoding="utf-8")

        for entity in topic.entities:
            assert f'"{entity.name}" [label=' in source, (
                f"{topic.name} ERD has no node for {entity.name}"
            )
            for field in entity.fields:
                assert f'PORT="{field.name}"' in source, (
                    f"{topic.name} ERD omits column {entity.name}.{field.name}"
                )

        for entity in topic.entities:
            for fk in entity.foreign_keys:
                edge = (
                    f'"{fk.referenced_entity}":"{fk.referenced_field}" -> '
                    f'"{entity.name}":"{fk.name}"'
                )
                assert edge in source, (
                    f"{topic.name} ERD is missing the relationship "
                    f"{entity.name}.{fk.name} -> {fk.references}"
                )


def test_erd_is_embedded_in_the_topic_page(repo_root: Path):
    """Somebody reading the docs should meet the diagram before the tables."""
    for topic in ALL_TOPICS:
        page = repo_root / "docs" / "topics" / f"{topic.name}.md"
        image = repo_root / "png" / topic.name / "erd.png"
        if not page.exists() or not image.exists():
            pytest.skip("docs or ERD not generated yet")

        text = page.read_text(encoding="utf-8")
        assert f"../../png/{topic.name}/erd.png" in text, (
            f"{page} does not embed the ERD image"
        )
        # The diagram must come before the column dictionary: a reader
        # should see the shape of the data before the detail of it.
        assert text.index("erd.png") < text.index("## Column dictionary")
