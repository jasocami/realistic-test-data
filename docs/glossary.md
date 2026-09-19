# Glossary

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](synthetic-data-guarantees.md).

Every abbreviation and domain term used anywhere in this repository. If you
hit one that is not here, that is a bug — please open an issue.

---

## Data and database terms

**BOM** — byte-order mark, three invisible bytes some tools put at the start
of a UTF-8 file. It makes the first column header read as `﻿id` instead
of `id`, which breaks naive parsers in a way that is genuinely hard to spot.
Our CSVs have none; `csv/_edge-cases/bom-utf8.csv` has one on purpose.

**CRLF** — carriage return plus line feed (`\r\n`), the Windows line
ending. Unix uses `\n` alone. Our files use `\n`;
`csv/_edge-cases/crlf.csv` uses `\r\n` on purpose, and `.gitattributes`
stops git from "helpfully" converting it.

**Cardinality** — how many rows on each side of a relationship. "One
hospital has many departments" is one-to-many.

**Check digit** — an extra character computed from the others so a typo can
be caught instantly. IBANs, VINs, barcodes and Spanish DNIs all carry one.

**Denormalised** — the same fact stored in more than one place, on purpose,
to avoid a join. `appointments.hospital_id` is derivable from the doctor but
stored anyway, as real schemas do.

**ERD** — Entity Relationship Diagram: a picture of the tables, their
columns and the links between them. One per topic in `png/<topic>/erd.png`.

**Foreign key (FK)** — a column pointing at another table's primary key.
Every one in this repository resolves.

**Grain** — what one row of a table represents. "One row per appointment."
The most useful sentence in any data dictionary and the most often missing.

**ISO-8601** — the international date and time format: `2025-03-14` and
`2025-03-14T09:30:00`. Unambiguous (unlike `03/14/25`) and it sorts
correctly as plain text, which is why every date here uses it.

**NDJSON** — newline-delimited JSON: one complete object per line, no
wrapping array. Streams with constant memory. See [json.md](formats/json.md).

**Orphan row** — a row whose foreign key points at something that does not
exist. There are none here.

**Primary key (PK)** — the column uniquely identifying a row. Always an
integer `id` in this repository.

**SHA** — here, a git commit hash: the long hexadecimal string identifying
one exact commit.

**Surrogate key** — a meaningless key invented for joining (`id`), as
opposed to a *business key* that means something to people (`mrn`, `sku`,
`vin`). Most tables here have both.

---

## Clinical

**HbA1c** — glycated haemoglobin, a blood test reflecting average blood
sugar over about three months. Above 5.7% suggests prediabetes. Rises with
age, which is why it shows the age correlation in this data.

**ICD-10** — the World Health Organization's *International Classification
of Diseases*, tenth revision. The standard code for recording what is wrong
with a patient. `E11.9` is type 2 diabetes. Real codes are used here.

**LOINC** — *Logical Observation Identifiers Names and Codes*, the
international standard for identifying laboratory tests. `4548-4` is HbA1c.

**MIR** — *Médico Interno Residente*, Spain's competitive medical residency.
"Esp. vía MIR" on a doctor means they completed specialty training.

**MRN** — Medical Record Number, a hospital's permanent identifier for a
patient. What goes on a wristband, because names are ambiguous.

**Reference range** — the values considered normal for a test. Outside it,
the result is flagged `LOW` or `HIGH`.

---

## Retail

**EAN-13** — the 13-digit barcode on almost every retail product. The
thirteenth digit is a check digit. A `84` prefix means Spain.

**ISBN-13** — the 13-digit book identifier. Structurally an EAN-13 barcode
with a `978` or `979` prefix, so the same check digit applies.

**SKU** — Stock Keeping Unit, a shop's own internal product code, as opposed
to the manufacturer's barcode.

**IVA** — *Impuesto sobre el Valor Añadido*, Spanish VAT. Three rates apply
to groceries: 21% general, 10% reduced, and 4% *superreducido* on staples
like bread, milk, eggs, fruit and vegetables.

---

## Finance

**BBAN** — Basic Bank Account Number, the country-specific part inside an
IBAN. Spain's is 20 digits.

**CIF** — the Spanish company tax identifier. A letter for the company type
(`B` = S.L., `A` = S.A.) then eight digits.

**DNI** — *Documento Nacional de Identidad*, the Spanish national ID: eight
digits plus a check letter computed modulo 23. `12345678Z`.

**IBAN** — International Bank Account Number. Validated by the "mod-97"
test: rearrange, convert letters to digits, and the whole thing modulo 97
must equal 1. Spanish IBANs are 24 characters.

**KYC** — *Know Your Customer*, the identity verification regulators require
of banks.

**PCI DSS** — *Payment Card Industry Data Security Standard*, the rules
governing how card data may be stored. Among other things it forbids storing
a full card number, which is why only the masked form and last four digits
appear here.

**Luhn** — the checksum every payment card number satisfies. Invented at IBM
in 1954 and still what validates the card number in a checkout form.

**MCC** — Merchant Category Code, the ISO 18245 four-digit code classifying
what a business sells. `5411` is grocery stores. Real codes are used here.

**NIE** — the equivalent of a DNI for foreign residents in Spain, with a
leading X, Y or Z.

**OHLC** — Open, High, Low, Close: the four prices summarising one trading
day, and what a candlestick chart draws. The high is always at least the
open and the close.

**French amortisation system** — a loan repaid in a constant monthly
payment, where the interest portion shrinks and the principal portion grows
each month. What Spanish mortgages use.

**S.L. / S.A.** — *Sociedad Limitada* and *Sociedad Anónima*, the Spanish
equivalents of Ltd and PLC.

---

## Automotive

**ITV** — *Inspección Técnica de Vehículos*, Spain's compulsory
roadworthiness test. First at four years old, then every two years until
ten, then annually.

**DGT** — *Dirección General de Tráfico*, Spain's traffic authority, which
issues driving licences and registration plates.

**MPV** — Multi-Purpose Vehicle, what a people carrier or minivan is called
in Europe.

**Segment** — the European vehicle size classification. A is a city car, C a
family hatchback, E an executive saloon.

**SUV** — Sport Utility Vehicle: a tall, high-riding body style.

**VIN** — Vehicle Identification Number, 17 characters, standardised by ISO
3779. Position 9 is a check digit, position 10 the model year. The letters
I, O and Q are banned because they look like 1 and 0.

**WMI** — World Manufacturer Identifier, the first three VIN characters
identifying who built the vehicle. The ones here are invented.

---

## Education

**Bachillerato** — Spanish pre-university education, ages 16–18, two years.

**CEIP** — *Colegio de Educación Infantil y Primaria*, a state primary school.

**Concertado** — a school privately run but state-funded. A Spanish middle
category with no direct equivalent in most countries.

**CAP** — *Certificado de Aptitud Pedagógica*, the teaching qualification
Spain required before the Máster en Formación del Profesorado replaced it.

**ESO** — *Educación Secundaria Obligatoria*, compulsory secondary education,
ages 12–16, four years.

**FP** — *Formación Profesional*, vocational training.

**IES** — *Instituto de Educación Secundaria*, a state secondary school.

**0–10 scale** — Spanish grades run 0 to 10, not A–F. Five is a pass. The
bands are *Suspenso* (<5), *Aprobado* (5–5.9), *Bien* (6–6.9), *Notable*
(7–8.9) and *Sobresaliente* (9–10).

---

## Tools and formats

**OCR** — Optical Character Recognition: extracting text from an image or a
scanned document. The PDFs here will come with the data they were rendered
from, so you can check what OCR read against the truth.

**PIL / Pillow** — the standard Python imaging library, used here to read
and write images.

**QR code** — the square two-dimensional barcode. Holds far more than a
linear barcode, which is why it is used for payment links and wristbands.

**UTF-8** — the character encoding used for every text file here. It can
represent every character in every language, which is what lets `María` and
`ñ` survive a round trip.

---

## Standards and reserved ranges

**DDC** — Dewey Decimal Classification, the library system that files books
by subject number (500 is science, 800 literature). A registered trademark
of OCLC. Used here only in a documentation example.

**OCLC** — Online Computer Library Center, the non-profit that owns and
licenses the Dewey Decimal Classification.


**CC BY 4.0** — the Creative Commons Attribution licence. Permits any use,
including commercial, provided you credit the source. Version 4.0 explicitly
covers *sui generis database rights*, which is why it suits a dataset. The
data here uses it.

**CC0** — a public-domain dedication that waives even attribution. Not used
here, but common in other data repositories.

**Sui generis database rights** — a European right that attaches to a
compiled database independently of copyright in the individual records.
Covered by CC BY 4.0 Section 4.

**RFC 2606** — the standard reserving `example.com`, `.org` and `.net` for
documentation and test data. Every email address here uses one.

**555-01xx** — the North American telephone range reserved for fiction.
Spain has **no equivalent**, which is why the phone-number guarantee here is
weaker; see
[synthetic-data-guarantees.md](synthetic-data-guarantees.md#telephone--valid-but-not-provably-unreachable-).

**Test card ranges** — `4111 11…`, `5555 55…`, `3782 82…`: numbers every
payment processor recognises as non-live. They pass Luhn but can never move
money.
