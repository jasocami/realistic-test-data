# Documentation

> ⚠️ **SYNTHETIC DATA.** Every record in this repository is invented.
> See [synthetic-data-guarantees.md](synthetic-data-guarantees.md).

**New here? Read these two, in this order.** Twenty minutes total, and you
will understand the whole repository.

1. **[Getting started](01-getting-started.md)** — download one file and load
   it, in four languages. Two minutes.
2. **[Trace a record](03-trace-a-record.md)** — follow one patient from a
   CSV row to a SQL join to a diagram. This is the page that makes
   everything else make sense.

Then **[run an example](examples/)** — nine scripts, all executed by the
test suite, so none of them is quietly broken.

---

## I want to…

| | |
|---|---|
| …grab a file and get on with it | [Getting started](01-getting-started.md) |
| …work out *which* file I need | [Choosing a file](02-choosing-a-file.md) |
| …see working code | [Worked examples](examples/) |
| …understand how the data fits together | [Trace a record](03-trace-a-record.md) |
| …know what a column means | [Topic reference](topics/) |
| …see the tables as a picture | [Schema diagrams](../png/) |
| …link a file into my own project | [Linking files](linking-files.md) |
| …know the quirks of a format | [Format guides](formats/) |
| …look up an abbreviation | [Glossary](glossary.md) |
| …add a new topic | [Adding a topic](generators/adding-a-topic.md) |
| …check this is safe to publish | [Synthetic-data guarantees](synthetic-data-guarantees.md) |

---

## Everything, by section

### Start here
- [01 — Getting started](01-getting-started.md)
- [02 — Choosing a file](02-choosing-a-file.md)
- [03 — Trace a record through the repository](03-trace-a-record.md)
- [Worked examples](examples/) — nine runnable scripts
- [Glossary](glossary.md) — every abbreviation used anywhere

### Using the data
- [Linking files into your project](linking-files.md) — CDN URLs, version pinning
- [Format guides](formats/): [csv](formats/csv.md) · [json](formats/json.md) ·
  [db](formats/db.md) · [png](formats/png.md) · [jpeg](formats/jpeg.md) ·
  [pdf](formats/pdf.md)

### Reference
- [Topic pages](topics/) — every table, every column, with an ER diagram:
  [clinical](topics/clinical.md) · [supermarket](topics/supermarket.md) ·
  [finance](topics/finance.md) · [automobile](topics/automobile.md) ·
  [education](topics/education.md)
- [Synthetic-data guarantees](synthetic-data-guarantees.md) — what is
  invented, what is real, and the one caveat worth knowing

### Contributing
- [Adding a topic](generators/adding-a-topic.md) — empty file to passing tests
- [CONTRIBUTING.md](../CONTRIBUTING.md) — setup and the rules
- [LICENSING.md](../LICENSING.md) — CC BY 4.0 for data, MIT for code
- [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md) — ICD-10, LOINC, MCC

---

## A note on how these pages are maintained

The topic pages and every folder README are **generated** from the schema
definitions in `generators/topics/`. They cannot drift out of date with the
data, because they are built from the same source as it.

The pages you are reading now are hand-written, and three test gates keep
them honest:

| Gate | What it enforces |
|---|---|
| `test_every_internal_markdown_link_resolves` | No broken links, anywhere |
| `test_documented_python_snippets_run` | Every Python example actually runs |
| `test_no_undefined_jargon` | Every abbreviation is in the glossary |
| `test_every_worked_example_runs` | Every script in `examples/` runs and prints output |

If you add a page, those run against it automatically.
