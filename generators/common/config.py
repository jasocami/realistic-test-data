"""
Repository-wide settings.
===============================================================================

WHAT IS THIS FILE?
------------------
The handful of values that appear in generated documentation and download
links. They live here rather than being hardcoded in a dozen templates, so
that renaming the repository is a one-line change.

IF YOU FORKED THIS REPOSITORY, EDIT `GITHUB_REPO` BELOW.
Otherwise every download link in your generated READMEs will point back at
the original repository instead of yours.
"""

from __future__ import annotations

#: "owner/name" on GitHub. Every raw and CDN link in the generated docs is
#: built from this.
GITHUB_REPO = "jasocami/realistic-test-data"

#: The released version people should pin to. Bump this when you tag a new
#: release after regenerating the data.
#:
#: WHY PINNING MATTERS: links that point at `main` follow the branch, so the
#: file changes underneath anyone using it the next time the data is rebuilt.
#: A tag is immutable. See docs/linking-files.md.
VERSION = "v0.1.0"

#: Where the CDN serves tagged files from. jsDelivr is preferred over
#: raw.githubusercontent.com for anything a program fetches: it sets correct
#: Content-Type headers, allows cross-origin requests from a browser, caches
#: globally, and is not rate-limited.
CDN_BASE = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO}@{VERSION}"

#: Raw GitHub, which always serves the latest commit on the default branch.
#: Fine for scratch work; unsuitable for anything you want to keep working.
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

#: Shown at the top of every generated page.
SYNTHETIC_BANNER = (
    "> ⚠️ **SYNTHETIC DATA.** Every record in this repository is invented. "
    "No real people, patients, accounts, vehicles or students appear here. "
    "See [synthetic-data-guarantees.md](../../docs/synthetic-data-guarantees.md)."
)


def cdn_url(path: str) -> str:
    """Pinned CDN link for a file, safe to hardcode into a project."""
    return f"{CDN_BASE}/{path}"


def raw_url(path: str) -> str:
    """Latest-commit raw link for a file. Changes when the data is rebuilt."""
    return f"{RAW_BASE}/{path}"
