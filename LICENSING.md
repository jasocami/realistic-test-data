# Licensing

This repository is dual-licensed. Which licence applies depends on which
part you are using.

| Part | Covers | Licence |
|---|---|---|
| **Data** | `csv/` `json/` `db/` `png/` `pdf/` `jpeg/` `schemas/` `docs/` | [CC BY 4.0](LICENSE) |
| **Code** | `build.py`, `generators/`, `tests/` | [MIT](LICENSE-CODE) |

Copyright © 2026 Jason Castillejos ([jasocami](https://github.com/jasocami)).

Both licences permit **commercial use**, modification and redistribution.
Both ask only that you credit the source.

---

## How to attribute

If you redistribute the data, publish something built on it, or include it
in a public product, keep a line like this somewhere reasonable — a README,
a credits page, a data-sources section:

```
realistic-test-data by Jason Castillejos (jasocami), licensed under CC BY 4.0
https://github.com/jasocami/realistic-test-data
```

Or in HTML:

```html
<a href="https://github.com/jasocami/realistic-test-data">realistic-test-data</a>
by Jason Castillejos, licensed under
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
```

GitHub will also render a **"Cite this repository"** button from
[`CITATION.cff`](CITATION.cff) if you prefer a formal citation.

---

## Do I need to attribute for internal testing?

**No.** Attribution obligations under CC BY apply when you *share* the
material — redistribute it, publish it, or display it publicly.

Downloading `patients.csv` into your own test suite and running it on your
own machines or CI is not sharing. You owe nothing. Credit is only expected
when other people see the data.

In practice:

| What you are doing | Attribution needed? |
|---|---|
| Using a CSV in your private test suite | No |
| Seeding a local or staging database | No |
| Publishing a tutorial or blog post using the data | Yes |
| Shipping the data inside a public product or demo | Yes |
| Republishing the files, or a modified version of them | Yes |
| Using the generator code in your own project | Keep the MIT notice |

---

## Why two licences?

CC BY 4.0 is built for data. Crucially it covers **sui generis database
rights** — the separate European right that attaches to a compiled dataset
regardless of whether the individual records are copyrightable. A software
licence does not address those, which is why a dedicated data licence is the
right instrument for the tables here.

MIT is the natural fit for the generator code, and every developer already
knows what it requires.

---

## Third-party material

This repository embeds a small number of codes from public classification
systems that are **not** covered by the licences above — ICD-10, LOINC and
ISO 18245 merchant category codes. They remain the property of their
respective owners.

See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for the details.

---

*This page explains the licences in plain language. The licences themselves
are the legally operative documents: [LICENSE](LICENSE) and
[LICENSE-CODE](LICENSE-CODE). Nothing here is legal advice.*
