# Choosing a file

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](synthetic-data-guarantees.md).

There are 203 files here. This page gets you to the right one.

---

## Start from what you are testing

| I'm testing… | Use | Why that one |
|---|---|---|
| A **CSV importer** | `csv/<topic>/*.csv` | Plain UTF-8, no BOM, RFC 4180 quoting |
| A CSV importer's **error handling** | `csv/_edge-cases/` | Empty, BOM, CRLF, ragged rows, wrong encoding |
| An **API response** shape | `json/<topic>/*.json` | Real `null`s, real numbers, nested bundle available |
| A **streaming** parser | `json/<topic>/*.ndjson` | One object per line, constant memory |
| **SQL joins**, an ORM, migrations | `db/<topic>/<topic>.sqlite` | Real foreign keys and indexes |
| **JSON Schema** validation | `schemas/<topic>/*.schema.json` | Generated from the same source as the data |
| A **file upload** widget | anything | Pick a few formats and sizes |
| **Charts** | `finance/stock_prices`, `clinical/lab_results` | OHLC data and age-correlated values |
| **Correlation / analytics** | `education/enrollments` | A real signal is buried in it, see below |
| **Recursive queries**, tree UI | `supermarket/categories` | Self-referencing parent/child |
| **Running totals**, statements | `finance/transactions` | A genuinely correct running balance |
| **Timelines**, audit trails | `automobile/ownership_history` | Contiguous, gapless ownership periods |
| **Money** and tax arithmetic | `supermarket/transactions` | Totals reconcile to the cent, three VAT rates |
| **Check-digit** validation | `finance/accounts`, `automobile/vehicles` | Valid IBANs, VINs, DNIs, EAN-13s |
| **Address** validation | any topic | Postal code, province, city and phone prefix all agree |
| **Name** parsing | any topic | Spanish two-surname names, accents, `ñ` |
| **Schema** documentation tools | `png/<topic>/erd.dot` | Graphviz source for every topic |

---

## Which topic?

All five have the same structure, so pick on subject matter:

| Topic | Reach for it when you want… |
|---|---|
| **clinical** | A classic parent-child hierarchy, medical coding systems, values that correlate with age |
| **supermarket** | The most ordinary business shape there is: catalogue, customers, transactions, line items |
| **finance** | Arithmetic that has to be exactly right — running balances, amortisation, OHLC |
| **automobile** | Long per-entity histories: owners, services and inspections over years |
| **education** | Data with a **signal in it** — attendance and grades genuinely correlate |

---

## Which format?

```
Do you need to query it with SQL?           → db/
Is it going into a browser or an API test?  → json/
Does a spreadsheet or pandas need it?       → csv/
Is the file itself the thing under test?    → csv|json|db|png/_edge-cases/
Do you want a picture of the schema?        → png/<topic>/erd.png
```

**Still unsure? Take the CSV.** It is the smallest, the most widely
supported, and every other format holds exactly the same records.

---

## How big are they?

Sizes are per topic, for the whole set of tables.

| Format | Size | Largest single file |
|---|---|---|
| `csv/` | ~1 MB | `education/attendance.csv`, 538 KB |
| `json/` | ~4 MB | `education/attendance.json`, 1.9 MB |
| `db/` | ~2 MB | one `.sqlite` per topic |
| `png/` | ~400 KB | the ERD |

Need more rows than that? Do not scrape — clone and turn the dial:

```bash
python build.py --topic finance --scale 100
```

Every relationship, check digit and running balance holds at any scale.

---

## The deliberate awkwardness

Some things in this data will look like bugs and are not. They are there so
your code meets them here rather than in production:

| You will find | Because |
|---|---|
| ~10% of patients with **no insurance policy** | Your `LEFT JOIN` needs something to miss |
| Empty `phone` and `email` columns | Real registration data has gaps |
| A Barcelona patient at a **Sevilla hospital** | People travel for specialist care |
| Discontinued products still in old sales | Filtering to `active = true` before joining loses rows |
| `end_date` empty on repeat prescriptions | An open-ended course is the normal case |
| Lab values **one hundredth** over the threshold | Borderline comparisons are where code breaks |
| Grades where SQL's `ROUND` disagrees | Binary floating point vs exact decimal |

Each one is explained in the column description for the field concerned.

---

## Next

- **[Worked examples](examples/)** — runnable scripts for each of the above
- [Trace a record](03-trace-a-record.md) — how it all fits together
- [Topic reference](topics/) — every column explained
