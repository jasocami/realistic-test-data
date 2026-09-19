# Working with the JSON files

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

`json/<topic>/<table>.json` — an array of objects, pretty-printed.
`json/<topic>/<table>.ndjson` — the same records, one per line, for the
largest table in each topic.

## Our conventions

| | |
|---|---|
| Structure | A top-level **array**, not an object |
| Formatting | Two-space indent, human-readable |
| Encoding | UTF-8, accents kept as characters (not `\uXXXX` escapes) |
| Nulls | A real `null`, never `""` or `"NULL"` |
| Numbers | JSON numbers, so arithmetic works without parsing |
| Dates | ISO-8601 strings — JSON has no date type |
| Key order | Matches the schema, and matches the CSV column order |

## Loading it

```python
import json
patients = json.load(open("json/clinical/patients.json", encoding="utf-8"))
```

```javascript
const patients = await fetch(url).then((r) => r.json());
```

## What is NDJSON, and why is it here?

Newline-delimited JSON: one complete object per line, no wrapping array, no
commas between records.

```
{"id":1,"mrn":"MRN-0000001","full_name":"Marcia Villar-Rovira"}
{"id":2,"mrn":"MRN-0000002","full_name":"César Amaro Egea"}
```

The regular `.json` file has to be downloaded and parsed **completely**
before you can look at the first record — the closing `]` could always be
followed by more. NDJSON can be streamed: read a line, parse it, use it,
discard it, with constant memory whatever the file size.

It is what log pipelines, BigQuery and most "export my data" endpoints
actually produce, so it is worth having a sample to test against.

```python
import json
with open("json/education/attendance.ndjson", encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)    # one record in memory at a time
```

## Validating against the schema

Every table has a generated JSON Schema in `schemas/<topic>/<table>.schema.json`:

```python
import json, jsonschema

schema = json.load(open("schemas/clinical/patients.schema.json"))
data = json.load(open("json/clinical/patients.json"))
jsonschema.validate(data, schema)     # raises if the data does not conform
```

The schema is generated from the same definitions as the data, so it always
matches — which makes it a good fixture for testing your own validation
layer.

## Common mistakes

**Decimals losing a trailing zero.** `19.90` in the CSV is `19.9` in JSON.
They are the same number; JSON just has no way to express significant
trailing zeros. If you need the two-decimal form, format on output.

**Assuming a date is a Date.** `"2025-03-14"` is a string. Every JSON parser
will leave it as one. Parse it yourself.

**Large files in the browser.** A 1.3 MB array parses fine; a 100 MB one
from `--scale 100` will block the main thread. Use the NDJSON variant and a
streaming parser.

## Deliberately broken files

`json/_edge-cases/` holds malformed and awkward JSON — trailing commas,
duplicate keys, deep nesting, `NaN` — for testing your error paths.
