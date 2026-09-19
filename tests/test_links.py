"""
Every internal link must resolve.
===============================================================================

WHAT IS THIS FILE?
------------------
It walks every Markdown file in the repository, extracts every link that
points at another file in the repository, and checks the target exists.

WHY IT EXISTS
-------------
Because the alternative does not work. This repository shipped for a while
with six broken documentation links, one of which -- the synthetic-data
banner -- appeared on roughly twenty-five generated pages. Nobody noticed,
because a broken relative link on GitHub is a 404 you only discover by
clicking it.

Generated pages make this worse rather than better: one wrong path in a
template becomes dozens of broken links at once. So the check is automatic.

WHAT IT DOES NOT CHECK
----------------------
External http(s) links. Those would make the suite depend on the network and
on somebody else's uptime, which is a bad trade for a test that should run
in under a second.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: [text](target) -- but not images preceded by "!", which are handled the
#: same way here anyway since an image target is also a file that must exist.
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

#: Directories that hold no documentation worth checking.
SKIP_DIRECTORIES = {".git", ".pytest_cache", "__pycache__", ".ruff_cache",
                    ".venv", "node_modules"}


def _markdown_files(repo_root: Path) -> list[Path]:
    return [
        path for path in sorted(repo_root.rglob("*.md"))
        if not any(part in SKIP_DIRECTORIES for part in path.parts)
    ]


def test_every_internal_markdown_link_resolves(repo_root: Path):
    """No link in any Markdown file may point at something that isn't there."""
    broken: list[str] = []

    for path in _markdown_files(repo_root):
        text = path.read_text(encoding="utf-8")

        for target in LINK_PATTERN.findall(text):
            # Skip external links, anchors and mailto.
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue

            # Strip any trailing anchor: "docs/faq.md#why" -> "docs/faq.md"
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue

            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                broken.append(
                    f"{path.relative_to(repo_root)} -> {target}"
                )

    assert not broken, (
        f"{len(broken)} broken internal link(s):\n  "
        + "\n  ".join(broken[:25])
        + ("\n  ..." if len(broken) > 25 else "")
    )


def test_generated_pages_link_to_the_synthetic_data_notice(repo_root: Path):
    """The banner on every generated page must point somewhere real.

    This is the specific link that was broken across two dozen pages, so it
    gets its own assertion with a message that says what to fix.
    """
    notice = repo_root / "docs" / "synthetic-data-guarantees.md"
    assert notice.exists(), (
        "docs/synthetic-data-guarantees.md is missing, and every generated "
        "folder README and topic page links to it."
    )

    pages = [
        path for path in _markdown_files(repo_root)
        if "SYNTHETIC DATA" in path.read_text(encoding="utf-8")
    ]
    assert len(pages) >= 10, (
        f"only {len(pages)} pages carry the synthetic-data banner -- it "
        f"should appear on every generated page"
    )


@pytest.mark.parametrize(
    "required",
    [
        "README.md",
        "LICENSE",
        "LICENSE-CODE",
        "requirements.txt",
        "docs/synthetic-data-guarantees.md",
        "docs/linking-files.md",
        "docs/generators/adding-a-topic.md",
    ],
)
def test_key_files_exist(repo_root: Path, required: str):
    """The files the README promises a reader must actually be there."""
    assert (repo_root / required).exists(), f"{required} is missing"
