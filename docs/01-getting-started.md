# Getting started

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](synthetic-data-guarantees.md).

## Just give me a file

```bash
curl -O https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv
```

That is it. No clone, no install. 800 rows of realistic patient data.

## Load it

**Python**

```python
# pip install pandas          <- needed for this snippet, nothing else here does
import pandas as pd

URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv"
patients = pd.read_csv(URL, dtype={"postal_code": str})
print(patients.head())
```

No pandas? The standard library is enough:

```python
import csv, urllib.request

URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv"
with urllib.request.urlopen(URL) as response:
    rows = list(csv.DictReader(response.read().decode("utf-8").splitlines()))
print(rows[0]["full_name"])
```

*(`dtype={"postal_code": str}` keeps the leading zero on codes like `08011`.)*

**JavaScript**

```javascript
const URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/json/clinical/patients.json";
const patients = await fetch(URL).then((r) => r.json());
console.log(patients[0].full_name);   // "Marcia Villar-Rovira"
```

**SQL**

```bash
curl -O https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/db/clinical/clinical.sqlite
sqlite3 clinical.sqlite "PRAGMA foreign_keys = ON;
                         SELECT full_name, blood_type FROM patients LIMIT 5;"
```

**Shell**

```bash
curl -s https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv | head -3
```

## Which file do I want?

| I'm testing… | Use |
|---|---|
| a CSV importer | `csv/<topic>/*.csv` |
| broken CSV handling | `csv/_edge-cases/` |
| an API response shape | `json/<topic>/*.json` |
| a streaming parser | `json/<topic>/*.ndjson` |
| SQL joins, an ORM, migrations | `db/<topic>/<topic>.sqlite` |
| JSON Schema validation | `schemas/<topic>/*.schema.json` |
| charts and dashboards | `finance/stock_prices`, `clinical/lab_results` |
| correlation / analytics demos | `education/enrollments` |

Five topics: `clinical`, `supermarket`, `finance`, `automobile`, `education`.

## ⚠️ Pin to a tag

The URLs above contain `@v0.1.0`. Keep it. A link to `/main/` follows the
branch, and the file will change the next time the data is regenerated.
See [linking-files.md](linking-files.md).

## Next

- **[Trace a record](03-trace-a-record.md)** — follow one patient through
  every format. The fastest way to understand the whole repository.
- [Topic reference](topics/) — every table, every column
- [Format guides](formats/) — conventions and gotchas per format
- [Glossary](glossary.md) — MRN, ICD-10, IBAN, VIN, EAN-13…
