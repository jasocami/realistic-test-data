# Working with the PDF files

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

## Status

PDF generation is planned but not yet implemented. See the repository
[README](../../README.md) for what has landed.

## What will be here

Documents rendered **from the data in this repository** — which is the point,
and what makes them more useful than a generic sample PDF:

| Topic | Documents |
|---|---|
| clinical | discharge summary, lab report, prescription, consent form (fillable) |
| supermarket | till receipt, supplier invoice, product catalogue (multipage) |
| finance | account statement (multipage), loan amortisation, payslip |
| automobile | sales contract, service invoice, ITV inspection report |
| education | report card, enrolment confirmation, exam timetable |

Because each document is rendered from rows that really exist in the CSV, a
PDF invoice comes with its own **ground truth**. If you are testing OCR or
document extraction, you can check what your pipeline read against what the
document was generated from — which is normally the hardest part of
evaluating an extraction pipeline.

`pdf/_edge-cases/` will hold the awkward ones: zero-byte, encrypted,
truncated, no text layer, a thousand pages.
