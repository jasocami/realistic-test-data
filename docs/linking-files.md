# Linking files into your project

> ⚠️ **SYNTHETIC DATA.** Everything here is invented.
> See [synthetic-data-guarantees.md](synthetic-data-guarantees.md).

You do not need to clone this repository. Every file can be fetched directly
over HTTPS, which is usually what you want when you just need a CSV to test
an importer.

---

## The one thing to get right: pin to a tag

```
✅  https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv
⚠️  https://raw.githubusercontent.com/jasocami/realistic-test-data/main/csv/clinical/patients.csv
```

The first URL contains `@v0.1.0` — a git tag. Tags are immutable, so that
file will return the same bytes forever.

The second follows the `main` branch. The next time the data is regenerated,
**the file changes underneath you**, and a test that passed yesterday starts
failing for reasons that have nothing to do with your code.

Use `main` for a quick look. Use a tag for anything you keep.

---

## Why jsDelivr rather than raw.githubusercontent.com

Both work. jsDelivr is better for anything a program fetches:

| | jsDelivr | GitHub raw |
|---|---|---|
| `Content-Type` | Correct per file type | Everything as `text/plain` |
| Browser `fetch()` | Permissive CORS | Blocked in many setups |
| Caching | Global CDN | None |
| Rate limits | None | Yes, and unannounced |
| Version pinning | `@v0.1.0` | Branch or commit SHA |

---

## Copy-paste by language

### Python

```python
# pip install pandas
import pandas as pd

URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv"
patients = pd.read_csv(URL, dtype={"postal_code": str})
print(patients.head())
```

Without pandas — the standard library is enough:

```python
import csv, urllib.request

URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv"
with urllib.request.urlopen(URL) as response:
    rows = list(csv.DictReader(response.read().decode("utf-8").splitlines()))
print(rows[0]["full_name"])
```

### JavaScript / TypeScript

```javascript
const URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/json/clinical/patients.json";

const patients = await fetch(URL).then((response) => response.json());
console.log(patients[0].full_name);
```

### Command line

```bash
curl -O https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv

# straight into a pipeline
curl -s https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/csv/clinical/patients.csv \
  | head -5
```

### SQL / SQLite

SQLite is a **binary** file, so it has to be downloaded before you can query
it — there is no streaming equivalent:

```bash
curl -O https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/db/clinical/clinical.sqlite
sqlite3 clinical.sqlite "PRAGMA foreign_keys = ON;
                         SELECT full_name, blood_type FROM patients LIMIT 5;"
```

To load the data into PostgreSQL or MySQL instead, use the gzipped dump:

```bash
curl -s https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/db/clinical/clinical.sql.gz \
  | gunzip | psql mydatabase
```

### Images in HTML or Markdown

```html
<img src="https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/png/clinical/erd.png"
     alt="Clinical schema diagram">
```

---

## Building a URL yourself

```
https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@VERSION/FORMAT/TOPIC/FILE
                                                 ───────  ──────  ─────  ────
                                                 v0.1.0   csv     clinical  patients.csv
```

- **FORMAT** — `csv`, `json`, `db`, `pdf`, `png`, `jpeg`, `schemas`
- **TOPIC** — `clinical`, `supermarket`, `finance`, `automobile`, `education`
- **FILE** — the table name plus the extension; see the folder README for the list

Every generated folder README lists its files with ready-made download links,
so browsing to [`csv/clinical/`](../csv/clinical/) is usually faster than
constructing a URL by hand.

---

## Streaming a large file

For the bigger tables, `.ndjson` lets you process a record at a time instead
of loading the whole array into memory:

```python
import json, urllib.request

URL = "https://cdn.jsdelivr.net/gh/jasocami/realistic-test-data@v0.1.0/json/education/attendance.ndjson"

with urllib.request.urlopen(URL) as response:
    for line in response:
        record = json.loads(line)
        ...   # one record in memory at a time
```

---

## If you need more rows than are published

Do not scrape the repository for a bigger dataset — clone it and turn the
dial instead:

```bash
git clone https://github.com/jasocami/realistic-test-data
cd realistic-test-data && pip install -r requirements.txt

python build.py --topic finance --scale 100     # 100× the rows
```

The relationships, the check digits and the running balances all hold at any
scale.
