# Worked examples

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

Runnable scripts. **Every one of these is executed by the test suite on
every build** — if an example breaks, CI goes red. They are not snippets
that once worked.

```bash
python docs/examples/01_load_csv_stdlib.py
```

No setup needed beyond `pip install -r requirements.txt`, except where a
script says otherwise at the top.

---

## The scripts

| | What it shows |
|---|---|
| [`01_load_csv_stdlib.py`](01_load_csv_stdlib.py) | Read a CSV with **no dependencies at all**. Why every value is a string, and why an empty field is ambiguous. |
| [`02_load_csv_pandas.py`](02_load_csv_pandas.py) | The same with pandas, avoiding the two traps: postal codes losing their leading zero, and empty strings becoming `NaN`. |
| [`03_load_json.py`](03_load_json.py) | What JSON gives you that CSV cannot — a real `null`, and numbers you can do arithmetic on without parsing. |
| [`04_stream_ndjson.py`](04_stream_ndjson.py) | Process 18,000 records holding **one at a time** in memory. |
| [`05_query_sqlite.py`](05_query_sqlite.py) | Five tables joined, plus the `PRAGMA foreign_keys = ON` everybody forgets. |
| [`06_validate_json_schema.py`](06_validate_json_schema.py) | Validate the data against its generated schema — then break it on purpose to see the error. |
| [`07_verify_check_digits.py`](07_verify_check_digits.py) | Recompute every IBAN, DNI, VIN, plate and barcode in the repository. 5,500 identifiers, zero invalid. |
| [`08_find_the_signal.py`](08_find_the_signal.py) | Discover the attendance/achievement correlation that nothing in the data announces. |
| [`queries.sql`](queries.sql) | Eight SQL queries, simplest to most involved. |

Run the SQL with:

```bash
sqlite3 db/clinical/clinical.sqlite < docs/examples/queries.sql
```

---

## Start with these two

**[`01_load_csv_stdlib.py`](01_load_csv_stdlib.py)** if you just want the
data. Forty lines, no dependencies, and it explains the two things about CSV
that catch people out.

**[`08_find_the_signal.py`](08_find_the_signal.py)** if you want to see why
this data is different from a random generator:

```
  attendance      pupils   mean grade
  --------------------------------------
  under 70%          30    4.43  █████████████
  70-80%             90    5.08  ███████████████
  80-90%            173    5.35  ████████████████
  90-100%          1257    6.53  ███████████████████
```

That gradient is real, and nothing in the published data computes one column
from the other. Both follow from a per-pupil factor that is never written to
any file.

---

## A note on other languages

These examples are Python and SQL, because those are what this repository
can **execute in its own test suite**. Short JavaScript and shell snippets
live in [linking-files.md](../linking-files.md) and
[01-getting-started.md](../01-getting-started.md), but Node is not a
dependency of this project, so those are not run by CI the way these are.

If you would like a verified JavaScript or R example, open an issue — it
needs a runtime added to the CI image, which is a deliberate decision rather
than an oversight.
