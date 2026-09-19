# Working with the CSV files

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

One file per table, in `csv/<topic>/<table>.csv`.

## Our conventions

| | |
|---|---|
| Encoding | UTF-8, **no** byte-order mark |
| Separator | Comma |
| Quoting | RFC 4180, minimal — only quoted when the value contains a comma, quote or newline |
| Line endings | `\n`, on every platform |
| Header | Always present, one row, column names exactly as in the schema |
| Dates | ISO-8601 — `2025-03-14`, `2025-03-14T09:30:00` |
| Decimals | Always two places — `19.90`, never `19.9` |
| Booleans | `true` / `false`, lowercase, to match JSON |
| Empty | A genuinely empty field — see the gotcha below |

## Loading it

```python
# pip install pandas
import pandas as pd
patients = pd.read_csv("csv/clinical/patients.csv", dtype={"postal_code": str})
```

```python
import csv
with open("csv/clinical/patients.csv", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
```

```javascript
import Papa from "papaparse";
const { data } = Papa.parse(text, { header: true, skipEmptyLines: true });
```

```bash
csvlook csv/clinical/patients.csv | head    # csvkit
duckdb -c "SELECT * FROM 'csv/clinical/patients.csv' LIMIT 5;"
```

## Common mistakes

**Empty string or missing value?** CSV cannot tell you. An empty field is
just two commas — there is no way to distinguish "" from NULL. We write
NULLs as empty, so `pandas` will give you `NaN` and `csv.DictReader` will
give you `""`. If the distinction matters to you, use the JSON files, which
have a real `null`.

**`NaN` where you expected a string.** pandas converts empty fields to
`NaN`, which turns an object column into a float column if *every* value is
empty. Pass `keep_default_na=False` if you want empty strings instead.

**Leading zeros disappearing.** Spanish postal codes like `01032` are
strings, not numbers. pandas will helpfully turn them into `1032`. Use
`dtype={"postal_code": str}` — or read the schema in
`schemas/<topic>/<table>.schema.json`, which declares the real types.

**Accented characters as mojibake.** The files are UTF-8. If `María` looks
like `MarÃ­a`, something in your stack assumed Latin-1. Open with
`encoding="utf-8"` explicitly.

**Excel mangling the file.** Double-clicking a UTF-8 CSV in Excel on Windows
breaks accents, because Excel expects a BOM. Use Data → From Text/CSV and
choose UTF-8, or open `csv/_edge-cases/bom-utf8.csv` to see the variant
Excel does like.

## Deliberately broken files

`csv/_edge-cases/` will hold files designed to break parsers — empty,
header-only, BOM-prefixed, CRLF, ragged rows, Latin-1 encoded — so you can
test the unhappy path on purpose. Not yet generated; see the repository
[README](../../README.md) for what has landed.
