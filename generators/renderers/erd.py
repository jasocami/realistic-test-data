"""
Entity-relationship diagrams, rendered to PNG.
===============================================================================

WHAT IS THIS FILE?
------------------
It draws one entity-relationship diagram per topic and writes it to
``png/<topic>/erd.png``.

An ERD shows every table as a box listing its columns, with lines joining
the tables that reference one another. It is the fastest way to understand
an unfamiliar database -- far faster than reading a column dictionary -- so
it belongs in the docs and in the folder READMEs.

WHY A PNG AS WELL AS THE MERMAID DIAGRAM?
-----------------------------------------
docs/topics/<topic>.md already contains a Mermaid diagram, which GitHub
renders natively. That covers reading the repository on GitHub.

The PNG covers everything else: pasting into a slide deck, a ticket, a wiki
that has no Mermaid support, or a printed handout. It also shows every
COLUMN, which the Mermaid version deliberately does not -- Mermaid's ER
syntax would make the page unreadably long.

HOW IT WORKS
------------
The diagram is built from exactly the same Entity definitions as everything
else in this repository, so it can never disagree with the data. We emit a
Graphviz DOT file using HTML-like table labels (one row per column) and let
`dot` lay it out.

THE ONE EXTERNAL DEPENDENCY IN THIS REPOSITORY
----------------------------------------------
Rendering needs the `dot` command from Graphviz, which is a system package
rather than a Python one:

    Debian / Ubuntu   sudo apt install graphviz
    macOS             brew install graphviz
    Fedora            sudo dnf install graphviz

If `dot` is missing the build SKIPS the diagrams with a clear message
instead of failing. The PNGs are committed to the repository, so anybody
who only wants to USE the data never needs Graphviz at all -- it is
required only to regenerate the images.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..common.schema import Entity, Topic

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
# Deliberately light-backgrounded and opaque. A transparent PNG with dark
# text becomes unreadable the moment somebody views the repository in
# GitHub's dark theme, so the image carries its own background.

COLOUR_BACKGROUND = "#ffffff"
COLOUR_HEADER_BG = "#1f2937"     # dark slate
COLOUR_HEADER_TEXT = "#ffffff"
COLOUR_ROW_BG = "#ffffff"
COLOUR_ROW_ALT_BG = "#f4f6f8"    # subtle banding, so long tables stay readable
COLOUR_TEXT = "#111827"
COLOUR_TYPE_TEXT = "#6b7280"     # muted: the type matters less than the name
COLOUR_BORDER = "#9ca3af"
COLOUR_EDGE = "#6b7280"

#: One colour per PARENT table, so every line leaving the same table shares
#: a hue. In a diagram with a dozen crossing relationships this is the
#: difference between tracing a line by eye and giving up: you follow the
#: colour rather than the geometry.
#:
#: Chosen to stay distinguishable on white, to survive greyscale printing
#: (the lightnesses differ, not just the hues), and to remain separable for
#: the most common forms of colour blindness -- no red/green pair carries
#: meaning on its own.
EDGE_PALETTE = [
    "#1d4ed8",  # blue
    "#b45309",  # amber
    "#047857",  # green
    "#7c3aed",  # violet
    "#be185d",  # pink
    "#0e7490",  # teal
    "#b91c1c",  # red
    "#4d7c0f",  # olive
    "#c2410c",  # orange
    "#334155",  # slate
]
COLOUR_PK = "#b45309"            # amber
COLOUR_FK = "#1d4ed8"            # blue
COLOUR_NULLABLE = "#9ca3af"

FONT = "DejaVu Sans"
FONT_MONO = "DejaVu Sans Mono"


def _escape(text: str) -> str:
    """Escape text for a Graphviz HTML-like label."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _key_marker(entity: Entity, field) -> tuple[str, str]:
    """Return the (marker text, colour) shown in a row's left column."""
    if field.primary_key:
        return "PK", COLOUR_PK
    if field.references:
        return "FK", COLOUR_FK
    return "", COLOUR_TEXT


def _entity_node(entity: Entity, row_count: int | None) -> str:
    """Render one table as a Graphviz HTML-like label.

    Each column becomes a table row with three cells: the key marker, the
    column name, and the type. Rows are given a PORT so that relationship
    lines can attach to the exact column they join on rather than to the
    middle of the box -- which is the difference between an ERD you can read
    and a bowl of spaghetti.
    """
    title = _escape(entity.name)
    if row_count is not None:
        title += f'  <FONT POINT-SIZE="9" COLOR="#9ca3af">{row_count:,} rows</FONT>'

    rows = [
        f'<TR><TD BGCOLOR="{COLOUR_HEADER_BG}" COLSPAN="3" ALIGN="LEFT">'
        f'<FONT COLOR="{COLOUR_HEADER_TEXT}" POINT-SIZE="13"><B>{title}</B></FONT>'
        f"</TD></TR>"
    ]

    for index, field in enumerate(entity.fields):
        marker, marker_colour = _key_marker(entity, field)
        background = COLOUR_ROW_ALT_BG if index % 2 else COLOUR_ROW_BG

        name = _escape(field.name)
        if field.primary_key:
            name = f"<B>{name}</B>"
        # A nullable column is shown in a lighter shade -- the quickest way
        # to see at a glance which parts of a row can be missing.
        name_colour = COLOUR_NULLABLE if field.nullable else COLOUR_TEXT

        type_label = _escape(field.type)
        if field.nullable:
            type_label += "?"

        # Graphviz rejects an empty text element -- "<B></B>" is a syntax
        # error, not an empty string -- so a column with no key marker gets
        # a genuinely empty cell rather than an empty font run.
        marker_cell = (
            f'<FONT COLOR="{marker_colour}" POINT-SIZE="9"><B>{marker}</B></FONT>'
            if marker else ""
        )

        rows.append(
            f'<TR><TD PORT="{_escape(field.name)}" BGCOLOR="{background}" '
            f'ALIGN="LEFT" WIDTH="26">{marker_cell}</TD>'
            f'<TD BGCOLOR="{background}" ALIGN="LEFT">'
            f'<FONT COLOR="{name_colour}" POINT-SIZE="11">{name}</FONT></TD>'
            f'<TD BGCOLOR="{background}" ALIGN="LEFT">'
            f'<FONT COLOR="{COLOUR_TYPE_TEXT}" POINT-SIZE="9" FACE="{FONT_MONO}">'
            f"{type_label}</FONT></TD></TR>"
        )

    table = (
        f'<TABLE BORDER="1" COLOR="{COLOUR_BORDER}" CELLBORDER="0" '
        f'CELLSPACING="0" CELLPADDING="4">' + "".join(rows) + "</TABLE>"
    )
    return f'  "{entity.name}" [label=<{table}>];'



def _legend_node() -> str:
    """A key explaining the notation, as a Graphviz node.

    It is placed in the leftmost rank alongside the root tables, which is
    where `dot` leaves empty space in a left-to-right layout -- so the key
    costs nothing in image size and fills a gap that would otherwise just
    be white.

    Worth having because crow's-foot notation is not self-explanatory to
    somebody meeting it for the first time, and this repository is meant to
    be readable by people who have never seen an ERD.
    """
    rows = [
        ("PK", COLOUR_PK, "primary key &#8212; join on this"),
        ("FK", COLOUR_FK, "foreign key &#8212; points at another table"),
        ("?", COLOUR_NULLABLE, "nullable &#8212; this column can be empty"),
    ]
    body = "".join(
        f'<TR><TD ALIGN="RIGHT" WIDTH="30">'
        f'<FONT COLOR="{colour}" POINT-SIZE="10"><B>{marker}</B></FONT></TD>'
        f'<TD ALIGN="LEFT"><FONT COLOR="{COLOUR_TEXT}" POINT-SIZE="10">'
        f"{text}</FONT></TD></TR>"
        for marker, colour, text in rows
    )

    # The relationship notation, spelled out. "One hospital has many
    # departments" is the sentence the symbols encode.
    body += (
        f'<TR><TD COLSPAN="2" ALIGN="LEFT">'
        f'<FONT COLOR="{COLOUR_TEXT}" POINT-SIZE="10">'
        f"&#8212;&#124; one &#160;&#160; &#8212;&#60; many</FONT></TD></TR>"
        f'<TR><TD COLSPAN="2" ALIGN="LEFT">'
        f'<FONT COLOR="{COLOUR_TYPE_TEXT}" POINT-SIZE="9">'
        f"line colour = parent table</FONT></TD></TR>"
    )

    return (
        f'  "__legend__" [label=<'
        f'<TABLE BORDER="1" COLOR="{COLOUR_BORDER}" CELLBORDER="0" '
        f'CELLSPACING="0" CELLPADDING="4" BGCOLOR="#fbfcfd">'
        f'<TR><TD BGCOLOR="{COLOUR_HEADER_BG}" COLSPAN="2" ALIGN="LEFT">'
        f'<FONT COLOR="{COLOUR_HEADER_TEXT}" POINT-SIZE="11"><B>how to read this</B></FONT>'
        f"</TD></TR>{body}</TABLE>>];"
    )


def build_dot(topic: Topic, row_counts: dict[str, int] | None = None) -> str:
    """Produce the Graphviz DOT source for one topic's ERD."""
    row_counts = row_counts or {}

    title_html = (
        f'<FONT POINT-SIZE="20" COLOR="{COLOUR_TEXT}"><B>{_escape(topic.title)}</B></FONT>'
        f'<BR/><BR/>'
        f'<FONT POINT-SIZE="11" COLOR="{COLOUR_TYPE_TEXT}">'
        f'realistic-test-data &#183; entity relationship diagram &#183; '
        f'{len(topic.entities)} tables</FONT>'
    )

    lines = [
        f'digraph "{topic.name}" {{',
        # rankdir=LR puts parents on the left and their children to the
        # right, which matches the direction the foreign keys point and
        # reads the way people expect an ERD to.
        f'  graph [rankdir=LR, bgcolor="{COLOUR_BACKGROUND}", pad=0.5,',
        f'         nodesep=0.4, ranksep=1.1, splines=spline, concentrate=false,',
        f'         fontname="{FONT}", labelloc="t", labeljust="l",',
        f'         label=<{title_html}>];',
        f'  node [shape=plaintext, fontname="{FONT}"];',
        f'  edge [color="{COLOUR_EDGE}", penwidth=1.2, arrowsize=0.9];',
        "",
    ]

    for entity in topic.build_order():
        lines.append(_entity_node(entity, row_counts.get(entity.name)))

    # Pin the key into the leftmost column, next to the tables that have no
    # foreign keys of their own. That column is the shortest, so this uses
    # space the layout was wasting.
    roots = [entity.name for entity in topic.entities if not entity.foreign_keys]
    lines.append("")
    lines.append(_legend_node())
    lines.append(
        "  { rank=min; " + " ".join(f'"{name}";' for name in ["__legend__", *roots]) + " }"
    )

    lines.append("")

    # Assign each parent table a colour, ordered by name so the mapping is
    # stable across rebuilds rather than depending on dict iteration order.
    parents = sorted({
        fk.referenced_entity
        for entity in topic.entities
        for fk in entity.foreign_keys
    })
    colour_by_parent = {
        parent: EDGE_PALETTE[index % len(EDGE_PALETTE)]
        for index, parent in enumerate(parents)
    }

    for entity in topic.entities:
        for fk in entity.foreign_keys:
            # Crow's-foot notation: a bar on the "one" end, a crow's foot on
            # the "many" end. A UNIQUE foreign key is one-to-one, so it gets
            # a bar at both ends instead.
            head = "tee" if fk.unique else "crow"
            colour = colour_by_parent[fk.referenced_entity]
            lines.append(
                f'  "{fk.referenced_entity}":"{fk.referenced_field}" -> '
                f'"{entity.name}":"{fk.name}" '
                f'[dir=both, arrowtail=tee, arrowhead={head}, '
                f'color="{colour}"];'
            )

    lines.append("}")
    return "\n".join(lines)


def graphviz_available() -> bool:
    """True if the `dot` command can be found on PATH."""
    return shutil.which("dot") is not None


def render_erd(
    topic: Topic,
    row_counts: dict[str, int] | None = None,
    root: Path = REPO_ROOT,
) -> Path | None:
    """Write ``png/<topic>/erd.png``.

    Returns the path, or None if Graphviz is not installed.
    """
    if not graphviz_available():
        return None

    output = root / "png" / topic.name / "erd.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    dot_source = build_dot(topic, row_counts)

    # Keep the DOT source alongside the image. It is a few kilobytes, it
    # diffs readably in a pull request when the schema changes, and it lets
    # anyone re-render at a different size or format without running the
    # whole build.
    dot_path = output.with_suffix(".dot")
    dot_path.write_text(dot_source, encoding="utf-8")

    subprocess.run(
        ["dot", "-Tpng", "-Gdpi=110", "-o", str(output)],
        input=dot_source.encode("utf-8"),
        check=True,
        capture_output=True,
    )
    return output


def render_all(
    topics: list[Topic],
    row_counts_by_topic: dict[str, dict[str, int]] | None = None,
    root: Path = REPO_ROOT,
) -> list[Path]:
    """Render an ERD for every topic. Returns the files written."""
    row_counts_by_topic = row_counts_by_topic or {}
    written = []
    for topic in topics:
        path = render_erd(topic, row_counts_by_topic.get(topic.name), root)
        if path is not None:
            written.append(path)
    return written
