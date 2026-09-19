# Working with the SQLite databases

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

`db/<topic>/<topic>.sqlite` — one database per topic, every table inside it.

Also in the folder:

| File | What it is |
|---|---|
| `<topic>.sqlite` | Ready to query. Real foreign keys, indexes on every FK. |
| `schema.sql` | Just the `CREATE TABLE` statements — a few KB, readable |
| `<topic>.sql.gz` | Structure **and** data as portable SQL, gzipped |

## Querying it

```bash
sqlite3 db/clinical/clinical.sqlite
```

```sql
PRAGMA foreign_keys = ON;          -- see the gotcha below

SELECT p.full_name, l.test_name, l.value, l.flag
FROM lab_results l
JOIN patients p ON p.id = l.patient_id
WHERE l.flag = 'HIGH'
LIMIT 10;
```

```python
import sqlite3
connection = sqlite3.connect("db/clinical/clinical.sqlite")
connection.execute("PRAGMA foreign_keys = ON;")
connection.row_factory = sqlite3.Row
```

## ⚠️ The gotcha that catches everybody

**SQLite does not enforce foreign keys by default.** It accepts the
constraint syntax and then ignores it, for backwards compatibility with very
old database files.

You must run this in **every connection**:

```sql
PRAGMA foreign_keys = ON;
```

It is not a property of the file — it is a property of the connection. Open
the database again and you have to set it again. Most ORMs do this for you;
raw `sqlite3` does not.

The data here satisfies every constraint whether you enable it or not; the
pragma matters when *you* start inserting.

## Loading into PostgreSQL or MySQL

```bash
gunzip -c db/clinical/clinical.sql.gz | psql mydatabase
gunzip -c db/clinical/clinical.sql.gz | mysql mydatabase
```

The dump is standard SQL, but note that SQLite's type system is looser than
either — you may want to adjust column types afterwards. `schema.sql` is the
place to start if you would rather define the tables yourself.

## Type mapping

SQLite has five storage classes, so our eight types map onto them:

| Our type | SQLite | Note |
|---|---|---|
| `integer` | `INTEGER` | |
| `decimal` | `REAL` | Money is computed in exact decimal then stored as REAL |
| `string`, `text`, `enum` | `TEXT` | Enums carry a `CHECK` constraint |
| `date`, `datetime` | `TEXT` | ISO-8601, which sorts correctly as text |
| `boolean` | `INTEGER` | `0` or `1` — SQLite has no boolean |

## Common mistakes

**Comparing dates as dates.** They are ISO-8601 strings. String comparison
works correctly for ordering (`WHERE d >= '2024-01-01'`), but use
`date()` / `julianday()` for arithmetic.

**Floating-point money.** `ROUND(SUM(score * weight), 2)` in SQLite is
binary floating point and can disagree with exact decimal arithmetic by a
cent. See the worked example on
[`education.grades`](../topics/education.md).

**Read-only filesystem.** SQLite wants to create a journal file next to the
database. Copy it somewhere writable before querying.
