"""
Turning schema definitions into readable documentation.
===============================================================================

WHAT IS THIS FILE?
------------------
It writes the Markdown that people actually read:

    docs/topics/<topic>.md      the full column dictionary and ER diagram
    <format>/<topic>/README.md  the page GitHub renders inside each folder
    <format>/README.md          an index of the topics in that format

None of it is hand-written. Every table, every column description and every
row count comes from the Entity definitions in generators/topics/ and from
the files that were just generated.

WHY GENERATE DOCUMENTATION INSTEAD OF WRITING IT?
-------------------------------------------------
Because written documentation goes stale and nobody notices. Add a column,
forget to update the Markdown table, and six months later someone is
debugging against a data dictionary that quietly lies to them.

Here that cannot happen. The description lives on the Field object, the CSV
header comes from the same Field object, and this file renders both. Change
one and everything moves together.

THE FOLDER README TRICK
-----------------------
GitHub renders a README.md inside *any* directory, right below the file
listing. So somebody who follows a link straight to csv/clinical/ -- which
is what happens when a colleague shares a deep link -- gets a full
explanation in place, rather than a bare list of filenames with no context.

That is 40-odd README files. Generating them is the only way that stays
accurate, and it costs nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common.config import SYNTHETIC_BANNER, cdn_url
from ..common.schema import Entity, Topic

REPO_ROOT = Path(__file__).resolve().parents[2]

#: What each format directory is for, in one sentence. Shown at the top of
#: the generated folder READMEs so the reader knows where they have landed.
FORMAT_BLURBS = {
    "csv": "Comma-separated values -- the most widely supported tabular format. "
           "One file per table, UTF-8, no byte-order mark, `\\n` line endings.",
    "json": "JSON arrays, pretty-printed and readable, plus `.ndjson` "
            "line-delimited versions of the larger tables for streaming.",
    "db": "SQLite databases with real foreign keys and indexes, plus a "
          "readable `schema.sql` and a gzipped portable SQL dump.",
    "pdf": "Documents rendered from the data in this repository -- an invoice "
           "PDF contains a transaction that really exists in the CSV.",
    "png": "Lossless graphics: charts, logos, barcodes, QR codes and diagrams.",
    "jpeg": "Lossy photographs and scans, carrying realistic EXIF metadata.",
}


def _escape_table_cell(text: str) -> str:
    """Make text safe to put inside a Markdown table cell.

    A literal `|` would end the cell early, and a newline would end the row.
    """
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _format_example(value: Any) -> str:
    """Render a Field's example value for a docs table."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return f"`{str(value).lower()}`"
    return f"`{value}`"


# ---------------------------------------------------------------------------
# The ER diagram
# ---------------------------------------------------------------------------

def render_er_diagram(topic: Topic) -> str:
    """Render the topic's tables and foreign keys as a Mermaid ER diagram.

    GitHub renders Mermaid natively inside a fenced ```mermaid block, so this
    shows up as an actual diagram on the repository page -- no image files,
    no build step, and it updates itself when the schema changes.

    Relationship notation:
        ||--o{   one-to-many   (one patient has many appointments)
        ||--o|   one-to-one    (one patient has at most one policy)
    """
    lines = ["```mermaid", "erDiagram"]

    for entity in topic.entities:
        for fk in entity.foreign_keys:
            # A UNIQUE foreign key means at most one child per parent.
            cardinality = "||--o|" if fk.unique else "||--o{"
            lines.append(
                f"    {fk.referenced_entity} {cardinality} {entity.name} : "
                f'"{fk.name}"'
            )

    # Tables with no relationships at all would otherwise vanish from the
    # diagram entirely, which would be misleading.
    connected = {e.name for e in topic.entities if e.foreign_keys}
    connected |= {
        fk.referenced_entity for e in topic.entities for fk in e.foreign_keys
    }
    for entity in topic.entities:
        if entity.name not in connected:
            lines.append(f"    {entity.name} {{")
            lines.append(f"        int id PK")
            lines.append("    }")

    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The column dictionary
# ---------------------------------------------------------------------------

def render_entity_section(entity: Entity, row_count: int | None = None) -> str:
    """Render one table's full documentation: grain, description, columns."""
    lines = [f"### `{entity.name}`", ""]

    if row_count is not None:
        lines.append(f"**{row_count:,} rows.** {entity.grain}")
    else:
        lines.append(f"{entity.grain}")
    lines.extend(["", entity.description.strip(), ""])

    lines.append("| Column | Type | Null | Description |")
    lines.append("|---|---|:---:|---|")

    for field in entity.fields:
        # Build the type cell: the base type, plus whatever qualifies it.
        type_parts = [f"`{field.type}`"]
        if field.primary_key:
            type_parts.append("**PK**")
        if field.references:
            type_parts.append(f"→ `{field.references}`")
        if field.unique and not field.primary_key:
            type_parts.append("unique")
        if field.unit:
            type_parts.append(f"_{field.unit}_")

        description = _escape_table_cell(field.description)
        if field.example is not None:
            description += f" Example: {_format_example(field.example)}"
        if field.type == "enum" and field.values:
            allowed = ", ".join(f"`{v}`" for v in field.values)
            description += f" One of: {allowed}"
        if field.pattern:
            description += f" Matches `{field.pattern}`"

        lines.append(
            f"| `{field.name}` | {' '.join(type_parts)} "
            f"| {'✓' if field.nullable else ''} | {description} |"
        )

    if entity.notes:
        lines.extend(["", "**Notes**", ""])
        lines.extend(f"- {note}" for note in entity.notes)

    lines.append("")
    return "\n".join(lines)


def render_topic_page(
    topic: Topic,
    row_counts: dict[str, int],
    formats: list[str],
    root: Path = REPO_ROOT,
) -> str:
    """Render the whole of docs/topics/<topic>.md.

    Only formats that actually contain files are listed. Advertising a
    download link for a file that has not been generated yet is worse than
    saying nothing -- it produces a 404 for the reader and makes every other
    link on the page look untrustworthy.
    """
    lines = [
        f"# {topic.title}",
        "",
        SYNTHETIC_BANNER.replace("../../docs/", "../"),
        "",
        "## What is this?",
        "",
        topic.description.strip(),
        "",
        "## Tables at a glance",
        "",
        "| Table | Rows | One row is... |",
        "|---|---:|---|",
    ]

    for entity in topic.build_order():
        count = row_counts.get(entity.name, 0)
        grain = _escape_table_cell(entity.grain).replace("One row per ", "")
        lines.append(f"| [`{entity.name}`](#{entity.name}) | {count:,} | {grain} |")

    lines.extend([
        "",
        "## How the tables relate",
        "",
        "Arrows point from the table that *owns* a row to the tables that "
        "*reference* it. Every foreign key in this diagram resolves -- there "
        "are no orphan rows anywhere in this topic.",
        "",
    ])

    # The rendered ERD shows every column and carries a key; the Mermaid
    # diagram below it is a lighter overview that GitHub draws natively.
    # Only link the image if it has actually been generated -- Graphviz is
    # optional, see generators/renderers/erd.py.
    if (root / "png" / topic.name / "erd.png").exists():
        lines.extend([
            f"[![{topic.title} entity relationship diagram]"
            f"(../../png/{topic.name}/erd.png)](../../png/{topic.name}/erd.png)",
            "",
            f"*Full-size: [`png/{topic.name}/erd.png`](../../png/{topic.name}/erd.png) "
            f"&middot; source: [`erd.dot`](../../png/{topic.name}/erd.dot). "
            f"Both are generated from the schema, so they cannot go stale.*",
            "",
            "<details><summary>Same diagram as Mermaid (renders inline on "
            "GitHub, without the columns)</summary>",
            "",
        ])
        lines.append(render_er_diagram(topic))
        lines.extend(["", "</details>", ""])
    else:
        lines.extend([render_er_diagram(topic), ""])

    lines.extend([
        "",
        "## Where to get it",
        "",
        "| Format | Path | Pinned download |",
        "|---|---|---|",
    ])

    sample = topic.entities[0].name
    for fmt in available_formats(topic, formats, root):
        if fmt == "db":
            path = f"db/{topic.name}/{topic.name}.sqlite"
        elif fmt == "schemas":
            path = f"schemas/{topic.name}/{sample}.schema.json"
        else:
            path = f"{fmt}/{topic.name}/{sample}.{fmt}"
        lines.append(f"| `{fmt}` | [`{fmt}/{topic.name}/`](../../{fmt}/{topic.name}/) "
                     f"| [`{Path(path).name}`]({cdn_url(path)}) |")

    lines.extend([
        "",
        "See [linking-files.md](../linking-files.md) for how to use these "
        "links from Python, JavaScript, SQL or the command line.",
        "",
        "## Column dictionary",
        "",
        "Every column, what it means, and whether it can be empty.",
        "",
    ])

    for entity in topic.build_order():
        lines.append(render_entity_section(entity, row_counts.get(entity.name)))

    lines.extend([
        "---",
        "",
        "*This page is generated from the schema definitions in "
        f"`generators/topics/{topic.name}.py`. Do not edit it by hand -- your "
        "changes would be overwritten on the next build. Edit the `description=` "
        "on the relevant `Field` instead, and run `python build.py`.*",
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Folder READMEs -- what GitHub shows inside each directory
# ---------------------------------------------------------------------------

def render_topic_folder_readme(
    topic: Topic,
    fmt: str,
    files: list[tuple[str, int, int | None]],
    siblings: list[str] | None = None,
) -> str:
    """Render <format>/<topic>/README.md.

    Parameters
    ----------
    files
        ``(filename, size_in_bytes, row_count_or_None)`` for each file in the
        folder.
    """
    lines = [
        f"# {topic.title} — `{fmt}`",
        "",
        SYNTHETIC_BANNER.replace("../../docs/", "../../docs/"),
        "",
        topic.summary,
        "",
        f"{FORMAT_BLURBS.get(fmt, '')}",
        "",
        "## Files",
        "",
        "| File | Rows | Size | Download |",
        "|---|---:|---:|---|",
    ]

    for filename, size, rows in sorted(files):
        row_cell = f"{rows:,}" if rows is not None else "—"
        path = f"{fmt}/{topic.name}/{filename}"
        lines.append(
            f"| `{filename}` | {row_cell} | {_human_size(size)} "
            f"| [download]({cdn_url(path)}) |"
        )

    lines.extend([
        "",
        f"## What the columns mean",
        "",
        f"Full column dictionary, with an entry for every field: "
        f"**[docs/topics/{topic.name}.md](../../docs/topics/{topic.name}.md)**",
        "",
        "## Related",
        "",
    ])

    for other in (siblings if siblings is not None else []):
        if other != fmt:
            lines.append(f"- The same data as [`{other}`](../../{other}/{topic.name}/)")

    lines.extend([
        "",
        "---",
        "",
        f"*Generated by `python build.py --topic {topic.name}`. Do not edit by hand.*",
        "",
    ])

    return "\n".join(lines)


def render_format_index(
    fmt: str, topics: list[Topic], root: Path = REPO_ROOT
) -> str:
    """Render <format>/README.md -- an index of the topics in this format.

    The `_edge-cases/` row is only included when that folder actually holds
    files. Linking to an empty or absent directory produces a 404 and makes
    every other link on the page look untrustworthy -- the same reason the
    format columns are existence-checked.
    """
    edge_cases = root / fmt / "_edge-cases"
    has_edge_cases = edge_cases.is_dir() and any(
        path.is_file() and path.name != "README.md" for path in edge_cases.iterdir()
    )

    lines = [
        f"# `{fmt}` files",
        "",
        FORMAT_BLURBS.get(fmt, ""),
        "",
        "## Topics",
        "",
        "| Topic | What's in it |",
        "|---|---|",
    ]

    for topic in topics:
        lines.append(
            f"| [`{topic.name}/`]({topic.name}/) | {_escape_table_cell(topic.summary)} |"
        )

    if has_edge_cases:
        lines.append(
            "| [`_edge-cases/`](_edge-cases/) | Deliberately awkward files — "
            "empty, malformed, wrongly encoded — for testing the unhappy "
            "path. |"
        )

    lines.extend([
        "",
        ""
        if has_edge_cases
        else "_Deliberately malformed `_edge-cases/` files for this format "
             "are planned but not yet generated._",
        "",
        f"## Working with `{fmt}` files",
        "",
        f"Conventions, gotchas and loading snippets in four languages: "
        f"**[docs/formats/{fmt}.md](../docs/formats/{fmt}.md)**",
        "",
        "---",
        "",
        "*Generated by `python build.py`. Do not edit by hand.*",
        "",
    ])

    return "\n".join(lines)


def available_formats(
    topic: Topic, formats: list[str], root: Path = REPO_ROOT
) -> list[str]:
    """Which of `formats` actually contain generated files for this topic.

    Used so the documentation never links to a file that does not exist yet.
    As the pdf/png/jpeg renderers land, those formats start appearing in the
    tables on their own -- no documentation change needed.
    """
    present = []
    for fmt in formats:
        folder = root / fmt / topic.name
        if folder.is_dir() and any(
            path.is_file() and path.name != "README.md" for path in folder.iterdir()
        ):
            present.append(fmt)
    return present


def _human_size(byte_count: int) -> str:
    size = float(byte_count)
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:,.0f} {unit}" if unit == "B" else f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} MB"


# ---------------------------------------------------------------------------
# The entry point the build calls
# ---------------------------------------------------------------------------

def write_topic_docs(
    topic: Topic,
    row_counts: dict[str, int],
    formats: list[str],
    root: Path = REPO_ROOT,
) -> list[Path]:
    """Write the topic page and every folder README for this topic."""
    written: list[Path] = []

    present = available_formats(topic, formats, root)

    # docs/topics/<topic>.md
    page = root / "docs" / "topics" / f"{topic.name}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        render_topic_page(topic, row_counts, formats, root), encoding="utf-8"
    )
    written.append(page)

    # <format>/<topic>/README.md
    for fmt in present:
        folder = root / fmt / topic.name
        if not folder.is_dir():
            continue

        files: list[tuple[str, int, int | None]] = []
        for path in sorted(folder.iterdir()):
            if path.name == "README.md" or not path.is_file():
                continue
            # Match a file back to its entity to report a row count.
            stem = path.name.split(".")[0]
            rows = row_counts.get(stem)
            files.append((path.name, path.stat().st_size, rows))

        if not files:
            continue

        readme = folder / "README.md"
        readme.write_text(
            render_topic_folder_readme(topic, fmt, files, siblings=present),
            encoding="utf-8",
        )
        written.append(readme)

    return written


def write_format_indexes(
    topics: list[Topic], formats: list[str], root: Path = REPO_ROOT
) -> list[Path]:
    """Write <format>/README.md for every format directory."""
    written = []
    for fmt in formats:
        folder = root / fmt
        if not folder.is_dir():
            continue
        # Skip a format directory that holds nothing but empty topic folders.
        has_content = any(
            child.is_file() and child.name != "README.md"
            for topic_dir in folder.iterdir() if topic_dir.is_dir()
            for child in topic_dir.iterdir()
        )
        if not has_content:
            continue
        readme = folder / "README.md"
        readme.write_text(render_format_index(fmt, topics, root), encoding="utf-8")
        written.append(readme)
    return written
