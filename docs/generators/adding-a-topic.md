# Adding a new topic

> ⚠️ **SYNTHETIC DATA.** Everything in this repository is invented.
> See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

This page walks through adding a whole new topic — a new set of related
tables, like `clinical` or `finance` — from an empty file to a passing test
suite.

It assumes you can write Python. It does **not** assume you have seen this
repository before.

**Time:** about an hour for a small topic. Most of that is writing the column
descriptions, which is deliberate — see [why the build makes you](#part-2--the-schema).

---

## Before you start

```bash
git clone https://github.com/jasocami/realistic-test-data
cd realistic-test-data

pyenv virtualenv 3.12.12 realistic-test-data     # or any Python 3.11+
pyenv local realistic-test-data
pip install -r requirements.txt -r requirements-dev.txt

python build.py --list                  # confirm it works
```

Then **open `generators/topics/clinical.py` and read it.** It is the
reference implementation and it is deliberately over-commented. Everything
below will make more sense if you have skimmed it first.

---

## The shape of a topic

A topic is one file, `generators/topics/<name>.py`, with three parts in this
order:

```
PART 1  Reference data   the real-world vocabularies you draw from
PART 2  The schema       one Entity per table, fully documented
PART 3  The generator    functions that produce the rows
```

…and a `TOPIC` object at the bottom tying it together.

That single file produces **everything**: the CSVs, the JSON, the SQLite
database, the JSON Schemas, the column dictionary in `docs/topics/`, the
folder READMEs, and the ERD image. You never write any of those by hand.

---

## Worked example: a `library` topic

We will build a small library system: branches, books, members, loans.

### Part 0 — create the file

```bash
cp generators/topics/clinical.py generators/topics/library.py
```

Starting from `clinical.py` and deleting is faster than starting from
nothing, because the structure and imports are already right.

### The imports

Every topic file starts with the same block. The snippets below are
**fragments** — they assume these imports are already at the top of your
file:

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from ..common.dates import add_years, next_weekday
from ..common.geography import PROVINCES, generate_address
from ..common.schema import Entity, Field, Topic
from ..common.seeds import Rng
```

### Part 1 — reference data

Put the real-world vocabularies at the top, as plain data. Keeping them
separate from the generation logic means somebody can see exactly what the
generator can produce without reading any code.

```python
DEFAULT_COUNTS = {
    "branches": 6,
    "members": 700,
    "books": 900,
    "loans": 2_500,
}

PERIOD_START = date(2023, 1, 1)
PERIOD_END = date(2025, 6, 30)

#: Real Dewey Decimal classes. A public classification system, not data
#: about anybody — using the genuine codes is what lets somebody test a
#: real catalogue lookup against this.
DEWEY_CLASSES = [
    ("000", "Computer science, information, general works", 40),
    ("100", "Philosophy and psychology", 25),
    ("300", "Social sciences", 60),
    ("500", "Natural sciences and mathematics", 55),
    ("800", "Literature", 90),
    ("900", "History and geography", 50),
]

LOAN_STATUSES = {"returned": 78, "on_loan": 15, "overdue": 6, "lost": 1}
```

Three conventions worth copying:

- **Weights, not uniform choices.** `{"returned": 78, "overdue": 6}` gives a
  realistic distribution. Uniform random selection is the single most
  obvious tell that data was generated rather than observed.
- **Real code systems where they exist.** Dewey, ICD-10, LOINC, ISO 18245 are
  public standards, not personal data. Using the genuine codes makes the
  data useful for testing a real lookup.
- **A fixed date window.** Never generate dates relative to "today" — the
  data would change meaning as time passed and rebuilds would stop being
  reproducible.

### Part 2 — the schema

This is where most of the work is, and where the build will push back.

```python
BOOKS = Entity(
    name="books",
    topic="library",
    grain="One row per distinct title held by the library.",
    description=(
        "The catalogue. A title, not a physical copy — several copies of "
        "the same book share one row here, which is why loans reference "
        "this table rather than an item table."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Use "
                          "this for joins rather than the ISBN."),
        Field("isbn13", "string", unique=True, pattern=r"^\d{13}$",
              example="9788412345678",
              description="The printed ISBN-13, thirteen digits with a "
                          "correct check digit — an ISBN is an EAN-13 with "
                          "the 978 or 979 prefix, so a barcode library will "
                          "decode these."),
        Field("title", "string", example="El jardín de las horas",
              description="Book title in Spanish, as it appears on the "
                          "spine. Invented, so no real published work is "
                          "named."),
        Field("dewey_class", "string", example="800",
              description="Dewey Decimal class, a genuine three-digit code "
                          "from the public classification scheme. 800 is "
                          "Literature, 500 Natural sciences."),
        Field("copies", "integer", unit="copies", example=3,
              description="How many physical copies the library holds, from "
                          "1 to 8. A title can never be on loan more times "
                          "than this at once."),
    ],
    notes=[
        "This table is titles, not copies. If you need item-level data, "
        "that is a different grain and would be a separate table.",
    ],
)
```

#### Why the build makes you write descriptions

Try leaving one out:

```python
Field("copies", "integer", example=3)
```

```
SchemaError: Field 'copies' has no description.

Every column in this repository must explain itself, because the generated
documentation is built from these descriptions and somebody who has never
seen this data has to understand the column from it alone.
```

The build **stops**. Not a warning — an exception. There are four rules:

| Rule | Why |
|---|---|
| Description required | The docs are generated from it |
| At least 40 characters | Stops `description="the id"` |
| At least 5 informative words | Stops descriptions that just restate the column name |
| `example=` required | One real value reads faster than a paragraph |
| `unit=` on measurements | `premium: 2480.00` — euros? cents? monthly? |

This feels obstructive for about ten minutes and then stops being
noticeable. It is the reason the column dictionaries in `docs/topics/` are
worth reading.

#### Finding every violation at once

The gate raises on the *first* bad field, which makes fixing a new topic a
slow one-at-a-time loop. To see them all:

```bash
python - <<'PY'
import sys; sys.path.insert(0, ".")
import generators.common.schema as schema
schema.MIN_DESCRIPTION_LENGTH = 0          # relax the hard gate
from generators.topics import library
for entity in library.TOPIC.entities:
    for field in entity.fields:
        if len(field.description.strip()) < 40 or field.example is None:
            print(f"{entity.name}.{field.name}: {field.description!r}")
PY
```

#### Grain is not optional either

```python
grain="One row per distinct title held by the library."
```

It must begin `"One row per …"` and be at least 25 characters. The grain is
the most useful sentence in any data dictionary and the one most often
missing: it tells a reader how to join the table and what a duplicate would
mean.

### Part 3 — the generator

One function per entity, each taking the rows it depends on as arguments.

```python
def _generate_loans(members, books, count):
    rng = Rng("library", "loans")          # own random stream — see below

    rows = []
    for index in range(1, count + 1):
        member = rng.python.choice(members)
        book = rng.python.choice(books)     # a real row, never an invented id

        borrowed_on = rng.date_between(
            max(PERIOD_START, member["joined_on"]), PERIOD_END
        )
        due_on = borrowed_on + timedelta(days=21)
        status = rng.weighted_choice(LOAN_STATUSES)

        rows.append({
            "id": index,
            "member_id": member["id"],
            "book_id": book["id"],
            "borrowed_on": borrowed_on,
            "due_on": due_on,
            "returned_on": due_on if status == "returned" else None,
            "status": status,
        })
    return rows
```

**The rule that makes foreign keys resolve:** never invent an ID. Always
pick an actual row and use its actual `id`. That single habit is why this
repository has zero orphan rows anywhere.

#### Every entity gets its own random stream

```python
rng = Rng("library", "loans")
```

`Rng` bundles Python's `random`, numpy's generator and Faker, all seeded from
the same derived seed — so it is impossible to seed two and forget the
third, which would quietly break reproducibility.

Deriving a separate stream per entity also keeps changes *local*. If every
entity shared one generator, adding a single book would shift the random
sequence for everything generated afterwards and the diff would show every
file changed.

#### Spanish data comes from `geography.py`, not Faker

```python
from ..common.geography import generate_address

location = generate_address(rng, with_phone=True, mobile=True)
# -> {"address": "Calle Mayor, 47, 3º B", "city": "Sevilla",
#     "province": "Sevilla", "postal_code": "41009",
#     "phone": "+34 954 21 08 33"}
```

Faker can give you an address, but it cannot make the postal code, the city,
the province and the telephone dialling prefix agree with each other.
`generate_address()` does, because a Spanish postal code's first two digits
*are* the province code. Use it for every address in every topic.

#### Money must use `Decimal`

```python
from decimal import Decimal

line_total = (quantity * unit_price).quantize(Decimal("0.01"))
```

Never `float`. `0.1 + 0.2` is not `0.3` in binary floating point, and across
thousands of rows those errors accumulate into totals that visibly do not
add up. See [the rounding note on `education.grades`](../topics/education.md)
for a worked example of what goes wrong.

#### Derived columns are computed from what you generated

If a column can be derived — a total, a rate, a band — compute it **from the
rows you already produced**, never alongside them. There is then only one
source of truth and the two cannot disagree. `_finalise_enrollments()` in
`education.py` is the pattern to copy.

### Part 4 — the `TOPIC` object

```python
TOPIC = Topic(
    name="library",
    title="Library / Lending",
    summary="Branches, a Dewey-classified catalogue, members and loans.",
    description=(
        "A Spanish municipal library service...\n\n"
        "Explain what makes this data realistic and what a reader can do "
        "with it. This paragraph becomes the introduction of the generated "
        "topic page, so write it for somebody who knows nothing about the "
        "domain."
    ),
    entities=[BRANCHES, MEMBERS, BOOKS, LOANS],   # any order; the build sorts
)


def generate(scale: float = 1.0) -> dict[str, list[dict]]:
    counts = {k: max(1, int(v * scale)) for k, v in DEFAULT_COUNTS.items()}

    branches = _generate_branches(counts["branches"])
    members = _generate_members(branches, counts["members"])
    books = _generate_books(counts["books"])
    loans = _generate_loans(members, books, counts["loans"])

    return {
        "branches": branches, "members": members,
        "books": books, "loans": loans,
    }
```

`generate()` must accept `scale` and return `{entity_name: [row dicts]}`.
The build topologically sorts the entities by their foreign keys, so parents
are always inserted before children.

---

## Register it

Two files, one line each.

**`build.py`:**

```python
from generators.topics import automobile, clinical, education, finance, library, supermarket

TOPICS = {
    ...
    "library": (library.TOPIC, library.generate),
}
```

**`tests/conftest.py`:**

```python
ALL_TOPICS = [..., library.TOPIC]
```

That second line matters more than it looks: adding it puts your topic
through the **entire existing test suite** — referential integrity,
cross-format equality, documentation completeness, reserved contact details,
reproducibility. You get roughly forty tests for one line.

---

## Build and check

```bash
python build.py --topic library
```

```
Library / Lending  (library)
  generated 4,106 rows across 4 tables in 0.1s
    branches                      6 rows        0.8 KB
    members                     700 rows       92.1 KB
    books                       900 rows       71.4 KB
    loans                     2,500 rows      143.2 KB
    docs                          4 pages
    erd                       png/library/erd.png
```

Then:

```bash
python -m pytest
```

Then **look at what you made** — the generated docs are the fastest review:

```bash
less docs/topics/library.md          # column dictionary + ERD
xdg-open png/library/erd.png         # the diagram
head -3 csv/library/loans.csv        # does the data look plausible?
```

---

## Add your own invariants

The shared tests check what is true of *every* topic. Your topic will have
rules of its own, and those are the valuable ones. Add them to
`tests/test_data_integrity.py`:

```python
def test_library_loans_never_exceed_available_copies(topic, topic_db):
    """A title cannot be on loan more times at once than copies exist."""
    if topic.name != "library":
        pytest.skip("library-specific invariant")

    impossible = topic_db.execute("""
        SELECT COUNT(*) FROM (
            SELECT l.book_id, COUNT(*) AS out_now
            FROM loans l WHERE l.status IN ('on_loan', 'overdue')
            GROUP BY l.book_id
        ) x JOIN books b ON b.id = x.book_id
        WHERE x.out_now > b.copies
    """).fetchone()[0]
    assert impossible == 0
```

Look at the existing ones for the pattern — the supermarket basket totals,
the finance running balances, the automobile odometer monotonicity.

---

## Common mistakes

**Rebuilding changes files that should not have changed.**
Something is not deterministic. Usual causes: iterating a `set` (unordered),
using `hash()` (randomised per process), calling `datetime.now()`, or
generating a date relative to today. Find it with
`python build.py --all && git status`.

**Foreign key violations on build.**
You invented an ID instead of taking one from a real row. Search your
generator for anything like `randint(1, len(parents))`.

**Timestamps disagree with a running total.**
If you sort rows by date but assign the time-of-day later, same-day rows end
up out of order relative to their sequence. Decide the *full* timestamp
before sorting. This bit me twice in `finance.py` — the comments there
explain it.

**`ValueError: day is out of range for month`.**
`some_date.replace(year=...)` on 29 February. Use `add_years()` and
`add_months()` from `generators/common/dates.py`.

**`sqlite3.OperationalError: near "s": syntax error`.**
An enum value contains an apostrophe (`"Children's"`) and reached a SQL
`CHECK` constraint unescaped. Already handled in `schema.py`, but the same
trap applies to any SQL you write yourself.

**The data parses fine but every chart looks like static.**
Your values are independent of one another. Real data correlates: older
patients have different lab results, diligent students attend more *and*
score higher. See the hidden diligence factor in `education.py` for how to
build a relationship in without publishing the cause of it.

---

## Checklist

- [ ] `generators/topics/<name>.py` with the three parts
- [ ] Every field has `description`, `example`, and `unit` where relevant
- [ ] Every entity has a `grain` starting `"One row per …"`
- [ ] Generators take parent rows as arguments and never invent IDs
- [ ] Money uses `Decimal`; addresses use `generate_address()`
- [ ] Registered in `build.py` **and** `tests/conftest.py`
- [ ] `python build.py --topic <name>` succeeds
- [ ] `python -m pytest` passes
- [ ] At least one topic-specific invariant test
- [ ] Rebuilding twice produces no `git status` changes
- [ ] You have looked at `docs/topics/<name>.md` and the ERD

---

## See also

- [`generators/topics/clinical.py`](../../generators/topics/clinical.py) — the commented reference implementation
- [`generators/common/schema.py`](../../generators/common/schema.py) — `Entity`, `Field`, and the documentation gate
- [`generators/common/geography.py`](../../generators/common/geography.py) — Spanish addresses, postal codes, phone numbers
- [`generators/common/identifiers.py`](../../generators/common/identifiers.py) — check digits: IBAN, VIN, EAN-13, DNI, Luhn
- [`generators/common/dates.py`](../../generators/common/dates.py) — leap-safe date arithmetic
