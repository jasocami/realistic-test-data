"""
Shared pytest fixtures.
===============================================================================

WHAT IS THIS FILE?
------------------
`conftest.py` is a file pytest looks for automatically. Anything defined here
as a `@pytest.fixture` can be requested by name as an argument in any test
function in this directory, and pytest will supply it.

So a test that starts:

    def test_something(clinical_db):

...gets an open SQLite connection without having to open one itself. If you
have not met pytest fixtures before, that is the whole trick: name the
fixture as a parameter and it appears.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from generators.common.schema import Topic  # noqa: E402
from generators.topics import (  # noqa: E402
    automobile,
    clinical,
    education,
    finance,
    supermarket,
)

#: Every topic that has been implemented. Tests iterate over this, so a new
#: topic is covered by the entire suite the moment it is added here.
ALL_TOPICS: list[Topic] = [
    clinical.TOPIC,
    supermarket.TOPIC,
    finance.TOPIC,
    automobile.TOPIC,
    education.TOPIC,
]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session", params=ALL_TOPICS, ids=lambda topic: topic.name)
def topic(request) -> Topic:
    """Runs the test once per topic.

    `params` is what makes this happen: pytest re-runs any test using this
    fixture once for each entry, so `test_x(topic)` becomes `test_x[clinical]`,
    `test_x[finance]` and so on as topics are added.
    """
    return request.param


@pytest.fixture(scope="session")
def topic_db(topic, repo_root) -> sqlite3.Connection:
    """An open connection to one topic's SQLite file, foreign keys enforced."""
    path = repo_root / "db" / topic.name / f"{topic.name}.sqlite"
    if not path.exists():
        pytest.skip(f"{path} has not been generated yet -- run `python build.py`")

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def read_csv(repo_root: Path, topic_name: str, entity_name: str) -> list[dict]:
    """Load one CSV file as a list of dicts."""
    path = repo_root / "csv" / topic_name / f"{entity_name}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(repo_root: Path, topic_name: str, entity_name: str) -> list[dict]:
    """Load one JSON file."""
    path = repo_root / "json" / topic_name / f"{entity_name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
