"""
Is the documentation usable by somebody who has never seen this repository?
===============================================================================

WHAT IS THIS FILE?
------------------
Two checks that documentation quality is real rather than intended:

1. Every Python snippet in the user-facing docs actually runs.
2. Every piece of jargon is defined in the glossary.

WHY BOTH ARE HERE
-----------------
These were promised early and not built, and the gap showed. The first
example a newcomer meets -- `import pandas as pd` in the README -- failed
with ModuleNotFoundError, because pandas was recommended in four documents
and listed in none. Nobody noticed, because nobody runs the documentation.

Now the test suite does.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

#: Documents whose Python snippets must be copy-paste runnable.
#:
#: The tutorial in docs/generators/ is deliberately excluded: it teaches by
#: showing fragments of a file in progress, which cannot run standalone and
#: should not pretend to. It states its imports up front instead.
RUNNABLE_SNIPPET_DOCS = [
    "README.md",
    "docs/01-getting-started.md",
    "docs/03-trace-a-record.md",
    "docs/linking-files.md",
    "docs/formats/csv.md",
    "docs/formats/json.md",
    "docs/formats/db.md",
    "docs/formats/png.md",
]

PYTHON_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _python_snippets(path: Path) -> list[str]:
    return PYTHON_FENCE.findall(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("document", RUNNABLE_SNIPPET_DOCS)
def test_documented_python_snippets_run(repo_root: Path, document: str):
    """Every Python example a reader might copy must actually work.

    Snippets that fetch over the network have their CDN URL rewritten to the
    equivalent local file, so the test stays offline and fast while still
    exercising the code around the fetch.
    """
    path = repo_root / document
    if not path.exists():
        pytest.skip(f"{document} not present")

    for index, code in enumerate(_python_snippets(path)):
        # Point network examples at the local copy of the same file.
        localised = re.sub(
            r'"https://cdn\.jsdelivr\.net/gh/[^@]+@[^/]+/([^"]+)"',
            lambda match: f'"{repo_root / match.group(1)}"',
            code,
        )
        # urllib cannot open a bare path; give it a file:// URL.
        localised = localised.replace(
            "urllib.request.urlopen(URL)",
            "urllib.request.urlopen('file://' + URL)",
        )

        if "https://" in localised:
            continue  # still remote after rewriting -- not ours to test

        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(f"import sys; sys.path.insert(0, {str(repo_root)!r})\n")
            handle.write(localised)
            script = handle.name

        result = subprocess.run(
            [sys.executable, script], capture_output=True, cwd=repo_root
        )
        assert result.returncode == 0, (
            f"{document} snippet #{index} fails when run:\n"
            f"--- code ---\n{code.strip()}\n"
            f"--- error ---\n{result.stderr.decode().strip()[-700:]}"
        )


# ---------------------------------------------------------------------------
# Jargon
# ---------------------------------------------------------------------------

#: Tokens that look like acronyms but are not domain jargon: file names,
#: format names a developer already knows, SQL keywords, Python names, and
#: words written in capitals for emphasis.
#:
#: Anything NOT on this list must appear in docs/glossary.md. When that
#: fails, the fix is almost always to define the term rather than to extend
#: this list -- the point is to make defining it the path of least
#: resistance.
NOT_JARGON = {
    # files and licences
    "README", "LICENSE", "LICENSE-CODE", "LICENSING", "CONTRIBUTING", "CITATION",
    "THIRD-PARTY", "NOTICES", "MIT", "CC0", "TODO", "NOTE",
    # formats and tech a developer already knows
    "CSV", "JSON", "SQL", "PDF", "PNG", "JPEG", "SVG", "HTML", "URL", "URLS",
    "HTTP", "HTTPS", "API", "CLI", "CDN", "CORS", "ORM", "ASCII", "RGB",
    "RGBA", "DOT", "GB", "MB", "KB", "CI", "PR", "OS", "UI", "ID", "IDS",
    "PY", "MD", "LR", "TB", "NAN", "GPS", "EXIF", "IANA", "IETF", "RFC",
    "ISO", "IEC", "GS1", "DPI",
    # our own notation, defined inline everywhere it appears
    "PK", "FK", "PART",
    # SQL and Python keywords appearing in prose
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "GROUP", "ORDER", "LIMIT",
    "COUNT", "SUM", "ROUND", "CREATE", "TABLE", "INSERT", "INTO", "VALUES",
    "PRAGMA", "INTEGER", "TEXT", "REAL", "CHECK", "UNIQUE", "KEY", "FOREIGN",
    "PRIMARY", "INDEX", "VIEW", "VACUUM", "LAG", "OVER", "PARTITION", "CASE",
    "WHEN", "THEN", "ELSE", "END", "DESC", "ASC", "NULL", "NULLS", "TRUE",
    "FALSE", "AND", "OR", "NOT", "IN", "IS", "ON", "AS", "BY", "TO", "IF",
    "IT", "NO", "SO", "ALL", "THE", "WHO",
    # currency codes -- self-evident in context, and all five appear in a
    # table that names them
    "EUR", "USD", "GBP", "CHF", "JPY", "MXN", "ES", "FR", "PT", "DE",
    # placeholders in URL templates
    "FILE", "TOPIC", "FORMAT", "VERSION", "XXX", "NNN",
    # words capitalised for emphasis in our own prose
    "FIND", "WARNING", "READING", "RECOMPUTATION", "DISAGREES", "AND",
    # Spanish sample text inside example values
    "COMPRA", "PLAZA", "SUPERMERCADO", "NOMINA", "CAJERO",
}

ACRONYM = re.compile(r"\b([A-Z][A-Z]+(?:-[A-Z0-9]+)?)\b")

SKIP_DIRECTORIES = {".git", ".pytest_cache", "__pycache__", ".ruff_cache", ".venv"}


def test_no_undefined_jargon(repo_root: Path):
    """Every acronym used in prose must be defined in the glossary.

    A junior who meets `MRN` or `mod-97` and cannot look it up learns that
    the documentation is not self-contained, and stops trusting it. So the
    glossary is not allowed to fall behind.
    """
    glossary_path = repo_root / "docs" / "glossary.md"
    glossary = glossary_path.read_text(encoding="utf-8").lower()

    undefined: dict[str, set[str]] = {}

    for path in sorted(repo_root.rglob("*.md")):
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if path.name == "glossary.md":
            continue

        text = path.read_text(encoding="utf-8")
        # Code blocks and inline code are not prose.
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]*`", "", text)

        for term in ACRONYM.findall(text):
            if term in NOT_JARGON or any(ch.isdigit() for ch in term):
                continue
            if term.lower() in glossary:
                continue
            undefined.setdefault(term, set()).add(str(path.relative_to(repo_root)))

    assert not undefined, (
        f"{len(undefined)} term(s) used but not defined in docs/glossary.md:\n  "
        + "\n  ".join(
            f"{term} — used in {', '.join(sorted(files)[:2])}"
            for term, files in sorted(undefined.items())
        )
        + "\n\nAdd them to the glossary, or to NOT_JARGON in this test if "
          "they genuinely need no explanation."
    )


# ---------------------------------------------------------------------------
# Worked examples
# ---------------------------------------------------------------------------

def _example_scripts(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "docs" / "examples").glob("*.py"))


def test_there_are_worked_examples(repo_root: Path):
    """docs/examples/ must not quietly become empty."""
    scripts = _example_scripts(repo_root)
    assert len(scripts) >= 5, (
        f"only {len(scripts)} example scripts found in docs/examples/"
    )


@pytest.mark.parametrize(
    "script",
    [path.name for path in sorted(Path(__file__).resolve().parents[1]
                                  .joinpath("docs/examples").glob("*.py"))],
)
def test_every_worked_example_runs(repo_root: Path, script: str):
    """Every script in docs/examples/ must run cleanly and print something.

    This is the gate the documentation examples did not have. A script that
    is committed but never executed is a script that is broken and nobody
    knows -- which is exactly what happened with the pandas snippets.
    """
    path = repo_root / "docs" / "examples" / script

    result = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        cwd=repo_root,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"docs/examples/{script} failed:\n"
        f"{result.stderr.decode().strip()[-800:]}"
    )
    assert result.stdout.strip(), (
        f"docs/examples/{script} ran but printed nothing -- an example that "
        f"shows no output teaches nothing."
    )


def test_example_sql_runs(repo_root: Path):
    """docs/examples/queries.sql must execute against the clinical database."""
    import shutil

    if shutil.which("sqlite3") is None:
        pytest.skip("the sqlite3 command-line tool is not installed")

    queries = repo_root / "docs" / "examples" / "queries.sql"
    database = repo_root / "db" / "clinical" / "clinical.sqlite"
    if not queries.exists() or not database.exists():
        pytest.skip("queries.sql or the database has not been generated")

    result = subprocess.run(
        ["sqlite3", str(database)],
        stdin=queries.open("rb"),
        capture_output=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"queries.sql failed:\n{result.stderr.decode().strip()[-800:]}"
    )
    # sqlite3 reports errors on stderr while still exiting 0 in some cases,
    # so check for them explicitly.
    stderr = result.stderr.decode()
    assert "Error" not in stderr, f"queries.sql reported: {stderr.strip()[:400]}"
    assert result.stdout.strip(), "queries.sql produced no output"
