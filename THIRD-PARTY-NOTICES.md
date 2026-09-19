# Third-party notices

Almost everything in this repository is generated and is covered by
[the licences described in LICENSING.md](LICENSING.md).

This page lists the exceptions: a small number of codes drawn from public
classification systems that this repository does **not** own and cannot
license to you. They remain the property of their respective owners, and the
CC BY 4.0 licence on the data does not extend to them.

They are included because using the *real* codes is what makes the data
useful — a terminology lookup, a coding validator or a categorisation rule
can be tested against them. Invented codes would look right and test
nothing.

---

## ICD-10 — 30 codes

**Source:** International Statistical Classification of Diseases and Related
Health Problems, 10th Revision
**Owner:** © World Health Organization
**Where:** `generators/topics/clinical.py` → `ICD10_CODES`, and the
`diagnoses` table in every format
**Used:** 30 codes with their official English titles

The WHO publishes ICD and asserts copyright over the classification. This
repository reproduces thirty code/title pairs — a very small extract, used
for interoperability testing rather than as a substitute for the
classification itself.

Reference: https://icd.who.int/

---

## LOINC — 20 codes

**Source:** Logical Observation Identifiers Names and Codes
**Owner:** © 1995–2026 Regenstrief Institute, Inc.
**Where:** `generators/topics/clinical.py` → `LAB_TESTS`, and the
`lab_results` table in every format
**Used:** 20 codes with their long common names

The notice Regenstrief asks users to carry:

> This material contains content from LOINC® (https://loinc.org). LOINC is
> copyright © 1995–2026, Regenstrief Institute, Inc. and the Logical
> Observation Identifiers Names and Codes (LOINC) Committee and is available
> at no cost under the licence at https://loinc.org/license.

LOINC is free to use and redistribute, with attribution — which is what this
section provides.

---

## ISO 18245 — 24 merchant category codes

**Source:** ISO 18245, *Retail financial services — Merchant category codes*
**Owner:** © International Organization for Standardization
**Where:** `generators/topics/finance.py` → `MERCHANT_CATEGORIES`, and the
`merchants` table in every format
**Used:** 24 four-digit codes with their category descriptions

MCC values are published by every card network and are in wide public
circulation; the ISO standard document itself is copyrighted and is not
reproduced here.

---

## Dewey Decimal Classification — 6 classes (documentation only)

**Owner:** © OCLC Online Computer Library Center, Inc.
**Where:** [`docs/generators/adding-a-topic.md`](docs/generators/adding-a-topic.md),
in a worked example only

Six top-level Dewey classes appear in a tutorial illustrating how to write a
new topic. No Dewey data is generated or published in any data file. DDC is
a registered trademark of OCLC.

---

## Standards referenced but not reproduced

These are algorithms and formats, implemented from their published
specifications. No copyrighted text is reproduced:

| | |
|---|---|
| ISO 3779 | VIN structure and check digit |
| ISO 13616 | IBAN structure and the mod-97 check |
| ISO/IEC 15420 | EAN-13 barcode check digit |
| ISO 8601 | Date and time format |
| RFC 4180 | CSV format |
| RFC 2606 | Reserved `example.com` domains |
| Spanish Royal Decree 1690/1986 | DNI check-letter algorithm |

---

## If you redistribute this data

The CC BY 4.0 licence covers the generated records — the invented patients,
products, accounts, vehicles and pupils, and the structure they sit in.

It does not, and cannot, grant you rights in the ICD-10, LOINC or MCC codes
listed above. If you are redistributing this data as part of a commercial
product, check those systems' own terms. For LOINC in particular, carry the
notice quoted above.

Nothing on this page is legal advice.
