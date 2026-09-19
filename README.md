# realistic-test-data

**Realistic, completely synthetic test data — in every format you actually need.**

> ⚠️ **SYNTHETIC DATA.** Every record here is invented. No real people, patients,
> accounts, vehicles or students appear anywhere in this repository.
> See [docs/synthetic-data-guarantees.md](docs/synthetic-data-guarantees.md).

---

## What is this?

A library of test files for developers: CSV, JSON, SQLite, PDF, PNG and JPEG,
organised by topic, with realistic relationships between them. Grab one file for
a quick test, or a whole relational dataset to seed a database.

It is different from the usual pile of sample files in two ways:

**The data is internally consistent.** Every foreign key resolves. An
appointment points at a patient who exists, seen by a doctor who really works at
that hospital. Addresses are Spanish and agree with themselves — the postal
code, province and telephone prefix all match the city. You can test joins,
cascades, orphan detection and address validation against it.

**The same records appear in every format.** `csv/clinical/patients.csv`,
`json/clinical/patients.json` and the `patients` table inside
`db/clinical/clinical.sqlite` hold the identical rows, in the identical
order. Benchmark a CSV parser against a JSON parser and you are measuring the
parser, not the data.

---

## Quick start

Grab a single file — no clone required:

```bash
curl -O https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv
```

Or load it straight into your code:

```python
# pip install pandas
import pandas as pd

URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv"
patients = pd.read_csv(URL, dtype={"postal_code": str})
```

```javascript
const URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/json/clinical/patients.json";
const patients = await fetch(URL).then(r => r.json());
```

```bash
curl -O https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/db/clinical/clinical.sqlite
sqlite3 clinical.sqlite "SELECT full_name, blood_type FROM patients LIMIT 5;"
```

⚠️ **Pin to a tag, not to `main`.** Links containing `@v0.1.0` are frozen
forever. Links to `/main/` follow the branch and will change under you the next
time the data is rebuilt. [More on linking →](docs/linking-files.md)

---

## Find your file

Folders are organised **format first, then topic**:

```
csv/clinical/patients.csv
└┬┘ └───┬──┘ └───┬─────┘
 │      │        └─ the table
 │      └─ the topic
 └─ the format
```

| Topic | Tables | Rows | CSV | JSON | SQLite | PDF | PNG | JPEG |
|---|---:|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| [**clinical**](docs/topics/clinical.md) — hospitals, patients, appointments, diagnoses, lab results | 9 | 15.4k | ✅ | ✅ | ✅ | ⏳ | ⏳ | ⏳ |
| [**supermarket**](docs/topics/supermarket.md) — stores, groceries, loyalty customers, till receipts | 10 | 16.2k | ✅ | ✅ | ✅ | ⏳ | ⏳ | ⏳ |
| [**finance**](docs/topics/finance.md) — accounts, cards, ledger, loans, market data | 10 | 16.3k | ✅ | ✅ | ✅ | ⏳ | ⏳ | ⏳ |
| [**automobile**](docs/topics/automobile.md) — vehicles, owners, dealers, servicing, ITV | 10 | 12.9k | ✅ | ✅ | ✅ | ⏳ | ⏳ | ⏳ |
| [**education**](docs/topics/education.md) — schools, pupils, courses, grades, attendance | 9 | 27.0k | ✅ | ✅ | ✅ | ⏳ | ⏳ | ⏳ |

✅ available · ⏳ in progress · every topic already ships a **schema diagram** (below)

### Schema diagrams

Each topic has a rendered entity-relationship diagram showing every table,
every column and every relationship, with a key explaining the notation:

| | | |
|---|---|---|
| [clinical](png/clinical/erd.png) | [supermarket](png/supermarket/erd.png) | [finance](png/finance/erd.png) |
| [automobile](png/automobile/erd.png) | [education](png/education/erd.png) | |

[![Clinical schema diagram](png/clinical/erd.png)](png/clinical/erd.png)

They are generated from the same schema definitions as the data, so they can
never drift out of date with it. Relationship lines are coloured by parent
table, which is what makes a dozen crossing foreign keys traceable by eye.
The Graphviz source sits next to each image as `erd.dot` if you want to
re-render at another size or format.

Each format folder also has an `_edge-cases/` directory: empty files, wrong
encodings, truncated images, malformed JSON — the awkward inputs that are hard
to produce yourself and are exactly what breaks software in production.

---

## "I want to test…"

| I'm testing… | Use |
|---|---|
| a CSV import or parser | `csv/<topic>/*.csv` |
| how my code handles broken CSV | `csv/_edge-cases/` |
| a REST API response shape | `json/<topic>/*.json` |
| a streaming / line-by-line parser | `json/<topic>/*.ndjson` |
| SQL joins, migrations, an ORM | `db/<topic>/<topic>.sqlite` |
| a file upload widget | anything — try a few formats and sizes |
| PDF text extraction or OCR | `pdf/<topic>/` (ground truth is in `csv/`) |
| image resizing, EXIF, thumbnails | `png/<topic>/`, `jpeg/<topic>/` |
| charts and dashboards | `finance/stock_prices` (OHLC), `clinical/lab_results` |
| correlation / analytics demos | `education/enrollments` — attendance vs grade |
| recursive queries, tree UI | `supermarket/categories` — self-referencing |
| running totals, statements | `finance/transactions` — true running balance |
| timelines and audit trails | `automobile/ownership_history`, `service_records` |
| JSON Schema validation | `schemas/<topic>/*.schema.json` |

---

## How realistic is it?

Realistic enough that you can plot it and the chart makes sense. Specifically,
these hold across the whole repository and are [verified in CI](tests/):

- **Every foreign key resolves** — zero orphan rows, enforced by SQLite itself
- **The money reconciles** — every supermarket basket's line totals sum exactly
  to what was charged, and the VAT breakdown adds up across all three Spanish
  rates (4%, 10%, 21%)
- **Running balances actually run** — order a bank account's transactions by
  time and each `balance_after` is the previous one plus the amount
- **Loans really amortise** — the French constant-payment system, reaching
  exactly zero at the final instalment
- **Odometers never run backwards** — a vehicle's mileage increases
  monotonically through its entire service and inspection history
- **There is a real signal to find** — in `education`, attendance and
  achievement correlate at r ≈ 0.44, driven by a hidden per-pupil factor that
  is never published. Random data has nothing to discover
- **Distributions are lopsided, not uniform** — blood types match real-world
  frequencies (O+ ~36%, AB− under 1%); 19.5% of pupils fail, as in Spain;
  Saturday is the busiest shopping day
- **Values correlate the way they should** — lab results use age-adjusted
  distributions, so mean HbA1c runs ~4.9% in under-35s against ~5.9% in over-70s
- **Derived columns agree with their sources** — a lab `flag` of `HIGH` really
  is above its reference range; a `grade_band` really follows from its score
- **Nothing happens before it could have** — no appointment precedes the
  patient's registration, no sale precedes the dealership opening
- **Identifiers carry valid check digits** — EAN-13 barcodes scan, Spanish IBANs
  pass mod-97, VINs pass ISO 3779, DNIs pass their modulo-23 letter, card
  numbers pass Luhn while staying in published non-live test ranges
- **Real code systems where they matter** — genuine ICD-10, LOINC and ISO 18245
  merchant category codes, so terminology lookups work

---

## Is it safe to publish?

Yes, by construction rather than by inspection:

- Email addresses only on `example.com` / `example.org` (reserved by RFC 2606)
- Card numbers only from published payment-processor test ranges
- Medical record numbers, licence numbers and VINs use invented formats
- Hospital and company names are invented — no real institution is named
- Images are generated programmatically — no copyright questions
- Every generator is in this repository, so you can verify all of the above

**One honest caveat about phone numbers.** The data is Spanish, and unlike
North America (which reserves `555-01xx` for fiction) Spain reserves no
numbers for test use. The numbers here are randomly generated and
structurally valid — which is what makes them useful for testing a validator
— but they cannot be *proven* unreachable the way a `555` number can. They
are not sampled from any real source and are not linked to any real person.
If you need an absolute guarantee, set `RESERVED_PHONES = True` in
`generators/common/geography.py` and rebuild.

---

## Rebuild or scale the data

Every file is generated. Nothing is hand-edited.

```bash
pyenv local realistic-test-data           # or: python -m pip install -r requirements.txt
pip install -r requirements.txt
sudo apt install graphviz        # optional — only needed to redraw the ERDs

python build.py --list           # what exists
python build.py --all            # rebuild everything
python build.py --topic clinical --scale 100   # 100x the rows, for load testing
```

Builds are **deterministic** — same seed, same output, byte for byte. Rebuilding
after a code change shows you exactly what your change affected and nothing else.

---

## Documentation

| | |
|---|---|
| [Getting started](docs/01-getting-started.md) | Download a file and load it, in four languages |
| [Choosing a file](docs/02-choosing-a-file.md) | "I'm testing X" → use this exact file |
| [Worked examples](docs/examples/) | Nine runnable scripts, all executed by CI |
| [Trace a record](docs/03-trace-a-record.md) | Follow one patient through every format — the fastest way to understand the whole repository |
| [Linking files into a project](docs/linking-files.md) | CDN URLs, version pinning, CORS |
| [Topic reference](docs/topics/) | Every table, every column, with ER diagrams |
| [Schema diagrams](png/) | Rendered ERDs, one per topic, with a notation key |
| [Format guides](docs/formats/) | Conventions and gotchas per format |
| [Adding a topic](docs/generators/adding-a-topic.md) | Full walkthrough: empty file → passing tests |
| [Synthetic-data guarantees](docs/synthetic-data-guarantees.md) | What is invented, what is real, and how it's enforced |
| [Contributing](CONTRIBUTING.md) | Setup and the rules |
| [Glossary](docs/glossary.md) | MRN, ICD-10, LOINC, IBAN, VIN, EAN-13, OHLC… |

Topic pages and folder READMEs are **generated from the schema definitions**, so
they can never drift out of date with the data. A column without a description
fails the build.

---

## Contributing

New topics are welcome — the generator framework does most of the work.
See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/generators/adding-a-topic.md](docs/generators/adding-a-topic.md).

## Licence

Copyright © 2026 Jason Castillejos ([jasocami](https://github.com/jasocami)).

| Part | Licence |
|---|---|
| **Data** — `csv/` `json/` `db/` `png/` `schemas/` `docs/` | [CC BY 4.0](LICENSE) |
| **Code** — `build.py` `generators/` `tests/` | [MIT](LICENSE-CODE) |

Both allow commercial use. Both ask only that you credit the source:

```
realistic-test-data by Jason Castillejos (jasocami), licensed under CC BY 4.0
https://github.com/jasocami/realistic-test-data
```

**Using it in your own test suite needs no attribution** — CC BY applies when
you *share* the material, not when you run it on your own machines. Full
detail, including a table of what does and doesn't need crediting, is in
[LICENSING.md](LICENSING.md).

A few ICD-10, LOINC and merchant-category codes belong to their respective
owners and are not covered by the above — see
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
