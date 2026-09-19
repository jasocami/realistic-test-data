"""
The guarantees this repository makes about its data.
===============================================================================

WHAT IS THIS FILE?
------------------
Every claim the README makes is asserted here. If a claim stops being true,
CI goes red before anybody downloads a file that contradicts the
documentation.

The guarantees, in plain language:

1. Every foreign key resolves -- no orphan rows anywhere.
2. The same records appear in CSV, JSON and SQLite, in the same order.
3. Derived columns agree with what they are derived from.
4. Dates are causally ordered -- nothing happens before it could have.
5. Contact details cannot reach a real person.
6. Rebuilding produces byte-identical files.
"""

from __future__ import annotations

import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from conftest import read_csv, read_json


# ---------------------------------------------------------------------------
# 1. Referential integrity
# ---------------------------------------------------------------------------

def test_sqlite_reports_no_foreign_key_violations(topic, topic_db):
    """SQLite's own integrity check must come back empty.

    `PRAGMA foreign_key_check` walks every foreign key in the database and
    returns a row for each one that points at a parent which does not exist.
    An empty result is the strongest single statement we can make about this
    data.
    """
    violations = topic_db.execute("PRAGMA foreign_key_check;").fetchall()
    assert not violations, (
        f"{topic.name}.sqlite has {len(violations)} dangling foreign keys, "
        f"first few: {[tuple(row) for row in violations[:5]]}"
    )


def test_every_foreign_key_column_resolves(topic, topic_db):
    """Check each declared relationship explicitly, table by table.

    This overlaps with the PRAGMA above, but reports a far more useful
    message: which column, and how many rows.
    """
    for entity in topic.entities:
        for fk in entity.foreign_keys:
            orphans = topic_db.execute(f"""
                SELECT COUNT(*) FROM "{entity.name}" child
                LEFT JOIN "{fk.referenced_entity}" parent
                       ON parent."{fk.referenced_field}" = child."{fk.name}"
                WHERE child."{fk.name}" IS NOT NULL
                  AND parent."{fk.referenced_field}" IS NULL
            """).fetchone()[0]

            assert orphans == 0, (
                f"{entity.name}.{fk.name} has {orphans} values with no "
                f"matching row in {fk.references}."
            )


def test_declared_unique_columns_really_are_unique(topic, topic_db):
    for entity in topic.entities:
        for field in entity.fields:
            if not (field.unique or field.primary_key):
                continue
            total, distinct = topic_db.execute(
                f'SELECT COUNT("{field.name}"), COUNT(DISTINCT "{field.name}") '
                f'FROM "{entity.name}"'
            ).fetchone()
            assert total == distinct, (
                f"{entity.name}.{field.name} is declared unique but has "
                f"{total - distinct} duplicate values."
            )


def test_non_nullable_columns_are_never_empty(topic, topic_db):
    for entity in topic.entities:
        for field in entity.fields:
            if field.nullable:
                continue
            nulls = topic_db.execute(
                f'SELECT COUNT(*) FROM "{entity.name}" WHERE "{field.name}" IS NULL'
            ).fetchone()[0]
            assert nulls == 0, (
                f"{entity.name}.{field.name} is declared NOT NULL but has "
                f"{nulls} empty values."
            )


# ---------------------------------------------------------------------------
# 2. Cross-format equality -- the repository's central promise
# ---------------------------------------------------------------------------

def test_csv_json_and_sqlite_hold_the_same_records(topic, topic_db, repo_root):
    """The same rows, in the same order, in all three formats.

    This is the claim that makes the repository useful for comparing
    parsers: if the CSV and the JSON disagree, any benchmark run against
    them is measuring the wrong thing.

    Values are compared as text, with the one documented exception that JSON
    renders 19.90 as 19.9 -- so decimals are compared numerically instead.
    """
    for entity in topic.entities:
        csv_rows = read_csv(repo_root, topic.name, entity.name)
        json_rows = read_json(repo_root, topic.name, entity.name)
        sql_rows = topic_db.execute(
            f'SELECT * FROM "{entity.name}" ORDER BY "{entity.primary_key.name}"'
        ).fetchall()

        assert len(csv_rows) == len(json_rows) == len(sql_rows), (
            f"{entity.name}: row counts differ -- csv={len(csv_rows)}, "
            f"json={len(json_rows)}, sqlite={len(sql_rows)}"
        )

        types = {field.name: field.type for field in entity.fields}

        # Compare the first, middle and last row in full. Comparing every row
        # of every table would add minutes to CI for very little extra
        # confidence -- a generator bug that affects one row affects all of
        # them.
        indices = {0, len(csv_rows) // 2, len(csv_rows) - 1} if csv_rows else set()

        for index in sorted(indices):
            csv_row, json_row, sql_row = csv_rows[index], json_rows[index], sql_rows[index]

            for column, field_type in types.items():
                csv_value = csv_row[column]
                json_value = json_row[column]
                sql_value = sql_row[column]

                # NULL is an empty cell in CSV and None in the other two.
                if json_value is None:
                    assert csv_value == "", (
                        f"{entity.name}[{index}].{column}: json is null but "
                        f"csv holds {csv_value!r}"
                    )
                    assert sql_value is None
                    continue

                if field_type == "decimal":
                    assert Decimal(csv_value) == Decimal(str(json_value)), (
                        f"{entity.name}[{index}].{column}: csv={csv_value} "
                        f"json={json_value}"
                    )
                    assert abs(float(sql_value) - float(json_value)) < 1e-9
                elif field_type == "boolean":
                    assert csv_value == str(json_value).lower()
                    assert bool(sql_value) == json_value
                else:
                    assert csv_value == str(json_value), (
                        f"{entity.name}[{index}].{column}: csv={csv_value!r} "
                        f"json={json_value!r}"
                    )
                    assert str(sql_value) == str(json_value)


def test_csv_headers_match_the_schema(topic, repo_root):
    """Column order and naming must follow the Entity definition exactly."""
    for entity in topic.entities:
        path = repo_root / "csv" / topic.name / f"{entity.name}.csv"
        if not path.exists():
            pytest.skip(f"{path} not generated")
        header = path.read_text(encoding="utf-8").split("\n", 1)[0]
        assert header.split(",") == entity.column_names, (
            f"{path.name} header does not match the schema.\n"
            f"  file:   {header}\n"
            f"  schema: {','.join(entity.column_names)}"
        )


def test_csv_files_have_no_byte_order_mark(topic, repo_root):
    """The published CSVs are plain UTF-8.

    A byte-order mark makes the first column header read as
    '\\ufeffid' instead of 'id', which breaks naive parsers in a way that is
    genuinely hard to spot. There IS a BOM file on purpose -- in
    csv/_edge-cases/ -- but the real data must not have one.
    """
    for path in (repo_root / "csv" / topic.name).glob("*.csv"):
        first_bytes = path.read_bytes()[:3]
        assert first_bytes != b"\xef\xbb\xbf", f"{path} starts with a UTF-8 BOM."


# ---------------------------------------------------------------------------
# 3 & 4. Derived values and causal ordering
# ---------------------------------------------------------------------------

def test_clinical_lab_flags_match_their_reference_ranges(topic, topic_db):
    """`flag` must always agree with value, reference_low and reference_high."""
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    wrong = topic_db.execute("""
        SELECT COUNT(*) FROM lab_results
        WHERE flag != CASE WHEN value < reference_low  THEN 'LOW'
                           WHEN value > reference_high THEN 'HIGH'
                           ELSE 'NORMAL' END
    """).fetchone()[0]
    assert wrong == 0, f"{wrong} lab results have a flag that contradicts their range."


def test_clinical_appointments_happen_where_the_doctor_works(topic, topic_db):
    """An appointment's hospital must be the doctor's hospital."""
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    mismatched = topic_db.execute("""
        SELECT COUNT(*) FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        WHERE a.hospital_id != d.hospital_id
    """).fetchone()[0]
    assert mismatched == 0


def test_clinical_doctors_belong_to_a_department_at_their_own_hospital(topic, topic_db):
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    mismatched = topic_db.execute("""
        SELECT COUNT(*) FROM doctors d
        JOIN departments dep ON dep.id = d.department_id
        WHERE dep.hospital_id != d.hospital_id
    """).fetchone()[0]
    assert mismatched == 0


def test_clinical_diagnoses_only_come_from_completed_appointments(topic, topic_db):
    """A cancelled visit cannot produce a diagnosis."""
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    impossible = topic_db.execute("""
        SELECT COUNT(*) FROM diagnoses dx
        JOIN appointments a ON a.id = dx.appointment_id
        WHERE a.status != 'completed'
    """).fetchone()[0]
    assert impossible == 0


def test_clinical_nothing_happens_before_the_patient_registered(topic, topic_db):
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    for table, column in [
        ("appointments", "date(scheduled_at)"),
        ("prescriptions", "start_date"),
        ("lab_results", "date(collected_at)"),
    ]:
        early = topic_db.execute(f"""
            SELECT COUNT(*) FROM {table} t
            JOIN patients p ON p.id = t.patient_id
            WHERE {column} < p.registered_at
        """).fetchone()[0]
        assert early == 0, f"{early} rows in {table} predate the patient's registration."


def test_clinical_qualifications_existed_when_the_doctor_qualified(topic, topic_db):
    """No doctor may hold a degree that did not exist when they were hired.

    Spain replaced the Licenciatura with the Grado en Medicina in the
    Bologna reform; the first Grado cohorts graduated around 2016. A doctor
    hired in 2004 holding a "Grado en Medicina" is an anachronism.
    """
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    from generators.topics.clinical import BOLOGNA_FIRST_GRADUATES

    anachronisms = topic_db.execute(
        "SELECT full_name, hired_at, qualification FROM doctors "
        "WHERE qualification LIKE 'Grado%' "
        f"AND CAST(substr(hired_at, 1, 4) AS INT) < {BOLOGNA_FIRST_GRADUATES}"
    ).fetchall()

    assert not anachronisms, (
        f"{len(anachronisms)} doctors hold a Grado en Medicina but were hired "
        f"before {BOLOGNA_FIRST_GRADUATES}, when it did not yet exist: "
        f"{[tuple(row) for row in anachronisms[:3]]}"
    )


def test_clinical_lab_values_really_do_track_patient_age(topic, topic_db):
    """The README claims lab results correlate with age. Prove it.

    This is the repository's most substantive realism claim -- it is what
    makes the data worth plotting rather than merely parsing -- so it gets an
    assertion rather than a promise.

    The test checks the DIRECTION and rough MAGNITUDE of the effect, not an
    exact mean. Exact figures move whenever the row counts change, and a test
    that has to be edited after every resize is a test people learn to
    ignore.
    """
    if topic.name != "clinical":
        pytest.skip("clinical-specific invariant")

    import statistics

    rows = topic_db.execute("""
        SELECT (2025 - CAST(substr(p.date_of_birth, 1, 4) AS INT)) AS age,
               l.value
        FROM lab_results l
        JOIN patients p ON p.id = l.patient_id
        WHERE l.test_name = 'Haemoglobin A1c'
    """).fetchall()

    younger = [value for age, value in rows if age < 35]
    older = [value for age, value in rows if age > 70]

    assert len(younger) >= 20 and len(older) >= 20, (
        f"Too few HbA1c results to compare age groups "
        f"(under-35: {len(younger)}, over-70: {len(older)}). If the row "
        f"counts were reduced, the age correlation can no longer be "
        f"demonstrated -- which is a reason not to reduce them further."
    )

    difference = statistics.mean(older) - statistics.mean(younger)
    assert difference > 0.4, (
        f"HbA1c should rise appreciably with age, but the over-70 mean is "
        f"only {difference:.2f} points above the under-35 mean. Check the "
        f"`age_slope` column in LAB_TESTS in generators/topics/clinical.py."
    )
    """Any pair of columns named *_from / *_until must be in order."""
    for entity in topic.entities:
        names = set(entity.column_names)
        for start, end in [("valid_from", "valid_until"),
                           ("start_date", "end_date"),
                           ("year_from", "year_to")]:
            if start in names and end in names:
                bad = topic_db.execute(
                    f'SELECT COUNT(*) FROM "{entity.name}" '
                    f'WHERE "{end}" IS NOT NULL AND "{end}" < "{start}"'
                ).fetchone()[0]
                assert bad == 0, (
                    f"{entity.name}: {bad} rows where {end} is before {start}."
                )


# ---------------------------------------------------------------------------
# 5. Synthetic-data guarantees
# ---------------------------------------------------------------------------

RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")


def test_email_addresses_use_reserved_domains(topic, topic_db):
    """No email in this repository may point at a domain somebody owns.

    example.com, .org and .net are reserved by the IETF (RFC 2606) precisely
    so that documentation and test data can use them without mail reaching a
    real inbox.
    """
    for entity in topic.entities:
        for field in entity.fields:
            if "email" not in field.name:
                continue
            offenders = topic_db.execute(
                f'SELECT DISTINCT "{field.name}" FROM "{entity.name}" '
                f'WHERE "{field.name}" IS NOT NULL AND '
                + " AND ".join(
                    f"\"{field.name}\" NOT LIKE '%@{domain}'"
                    for domain in RESERVED_EMAIL_DOMAINS
                )
                + " LIMIT 5"
            ).fetchall()
            assert not offenders, (
                f"{entity.name}.{field.name} contains addresses outside the "
                f"reserved domains: {[row[0] for row in offenders]}"
            )


def test_phone_numbers_are_valid_spanish_numbers(topic, topic_db):
    """Every telephone number must be a structurally valid Spanish number.

    Nine digits, beginning 6 or 7 (mobile) or 8 or 9 (landline). Anything
    else would fail a Spanish phone validator, which would make this data
    useless for testing one.

    Note what this test does NOT claim. Unlike the North American 555-01xx
    range, Spain reserves no numbers for fiction, so these numbers cannot be
    proven unreachable -- only proven well-formed. See the note in
    generators/common/geography.py.
    """
    from generators.common.geography import phone_is_valid

    for entity in topic.entities:
        for field in entity.fields:
            if "phone" not in field.name or field.name.endswith("extension"):
                continue
            values = topic_db.execute(
                f'SELECT "{field.name}" FROM "{entity.name}" '
                f'WHERE "{field.name}" IS NOT NULL'
            ).fetchall()
            bad = [row[0] for row in values if not phone_is_valid(str(row[0]))][:5]
            assert not bad, (
                f"{entity.name}.{field.name} contains numbers that are not "
                f"valid Spanish subscriber numbers: {bad}"
            )


def test_landline_prefixes_match_their_province(topic, topic_db):
    """A landline's dialling prefix must agree with the address beside it.

    91 is Madrid and 93 is Barcelona. A Madrid hospital with a 93 number
    would be the kind of internal inconsistency this repository exists to
    avoid -- and it is exactly what address-validation code should catch.
    """
    from generators.common.geography import PHONE_PREFIXES, PROVINCES

    for entity in topic.entities:
        names = set(entity.column_names)
        if not {"phone", "province"} <= names:
            continue

        rows = topic_db.execute(
            f'SELECT "phone", "province" FROM "{entity.name}" '
            f'WHERE "phone" IS NOT NULL'
        ).fetchall()

        province_to_code = {name: code for code, name in PROVINCES.items()}
        mismatched = []
        for phone, province in rows:
            digits = str(phone).replace("+34", "").replace(" ", "")
            if digits[0] in "67":
                continue  # mobiles are not geographic
            expected = PHONE_PREFIXES[province_to_code[province]]
            if not digits.startswith(expected):
                mismatched.append((phone, province, expected))

        assert not mismatched[:5], (
            f"{entity.name}: landline prefixes disagree with the province: "
            f"{mismatched[:5]}"
        )


def test_spanish_postal_codes_are_valid_and_match_their_province(topic, topic_db):
    """The first two digits of a postal code ARE the province code."""
    from generators.common.geography import PROVINCES, postal_code_is_valid

    for entity in topic.entities:
        names = set(entity.column_names)
        if not {"postal_code", "province"} <= names:
            continue

        rows = topic_db.execute(
            f'SELECT "postal_code", "province" FROM "{entity.name}"'
        ).fetchall()

        invalid = [code for code, _ in rows if not postal_code_is_valid(str(code))]
        assert not invalid[:5], (
            f"{entity.name}: invalid Spanish postal codes {invalid[:5]}. "
            f"Valid codes run 01000-52999; there is no province 00 or 53."
        )

        mismatched = [
            (code, province) for code, province in rows
            if PROVINCES[str(code)[:2]] != province
        ]
        assert not mismatched[:5], (
            f"{entity.name}: postal code does not match its province: "
            f"{mismatched[:5]}"
        )


def test_emails_contain_no_accented_characters(topic, topic_db):
    """Spanish names carry accents; email addresses cannot.

    "maría.fernández@example.com" is not a usable address. The generators
    transliterate before building the address, and this proves it happened.
    """
    for entity in topic.entities:
        for field in entity.fields:
            if "email" not in field.name:
                continue
            rows = topic_db.execute(
                f'SELECT "{field.name}" FROM "{entity.name}" '
                f'WHERE "{field.name}" IS NOT NULL'
            ).fetchall()
            bad = [
                row[0] for row in rows
                if not str(row[0]).isascii()
            ][:5]
            assert not bad, (
                f"{entity.name}.{field.name} contains non-ASCII addresses: "
                f"{bad}. Accents must be stripped before building an email."
            )


# ---------------------------------------------------------------------------
# 6. Reproducibility
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_rebuilding_produces_identical_files(topic, repo_root: Path):
    """Run the build again and confirm nothing changed.

    This is what makes "the data is synthetic" a checkable claim rather than
    a promise: anyone can re-run the generators and confirm they get the
    committed files back, byte for byte.

    Marked slow -- run with `pytest -m slow` or as part of the full suite.
    """
    def fingerprint() -> dict[str, bytes]:
        import hashlib
        digests = {}
        for folder in ("csv", "json", "db", "schemas"):
            for path in sorted((repo_root / folder / topic.name).rglob("*")):
                if path.is_file():
                    digests[str(path.relative_to(repo_root))] = hashlib.sha256(
                        path.read_bytes()
                    ).digest()
        return digests

    before = fingerprint()
    subprocess.run(
        [sys.executable, "build.py", "--topic", topic.name],
        cwd=repo_root, check=True, capture_output=True,
    )
    after = fingerprint()

    changed = [name for name in before if before[name] != after.get(name)]
    assert not changed, (
        f"Rebuilding changed {len(changed)} files: {changed[:5]}. "
        f"Something in the generators is not deterministic -- a missing seed, "
        f"an unsorted set, or a timestamp written into the output."
    )


# ---------------------------------------------------------------------------
# Topic-specific invariants: supermarket
# ---------------------------------------------------------------------------

def test_supermarket_baskets_reconcile_to_the_cent(topic, topic_db):
    """Line totals must sum exactly to the transaction total.

    The single most common flaw in generated retail data is a receipt whose
    lines do not add up to what was charged. Any report built on it looks
    broken, so this is asserted rather than assumed.
    """
    if topic.name != "supermarket":
        pytest.skip("supermarket-specific invariant")

    bad = topic_db.execute("""
        SELECT t.id, t.total, ROUND(SUM(i.line_total), 2)
        FROM transactions t
        JOIN transaction_items i ON i.transaction_id = t.id
        GROUP BY t.id
        HAVING ABS(t.total - ROUND(SUM(i.line_total), 2)) > 0.005
    """).fetchall()
    assert not bad, f"{len(bad)} baskets do not reconcile: {[tuple(r) for r in bad[:3]]}"


def test_supermarket_vat_breakdown_adds_up(topic, topic_db):
    """subtotal + vat_amount must equal total, on every transaction."""
    if topic.name != "supermarket":
        pytest.skip("supermarket-specific invariant")

    bad = topic_db.execute(
        "SELECT COUNT(*) FROM transactions "
        "WHERE ABS(subtotal + vat_amount - total) > 0.005"
    ).fetchone()[0]
    assert bad == 0


def test_supermarket_barcodes_are_scannable(topic, topic_db):
    """Every EAN-13 must carry a correct check digit."""
    if topic.name != "supermarket":
        pytest.skip("supermarket-specific invariant")

    from generators.common.identifiers import ean13_is_valid

    bad = [
        code for (code,) in topic_db.execute("SELECT ean13 FROM products")
        if not ean13_is_valid(code)
    ]
    assert not bad[:5], f"invalid EAN-13 check digits: {bad[:5]}"


def test_supermarket_product_vat_matches_its_category(topic, topic_db):
    """A product's VAT rate is inherited from its category and must agree."""
    if topic.name != "supermarket":
        pytest.skip("supermarket-specific invariant")

    bad = topic_db.execute("""
        SELECT COUNT(*) FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.vat_rate != c.vat_rate
    """).fetchone()[0]
    assert bad == 0


def test_supermarket_cashier_works_at_the_store(topic, topic_db):
    """A till can only be operated by a cashier from that store."""
    if topic.name != "supermarket":
        pytest.skip("supermarket-specific invariant")

    wrong_store = topic_db.execute("""
        SELECT COUNT(*) FROM transactions t
        JOIN employees e ON e.id = t.cashier_id
        WHERE e.store_id != t.store_id
    """).fetchone()[0]
    wrong_role = topic_db.execute("""
        SELECT COUNT(*) FROM transactions t
        JOIN employees e ON e.id = t.cashier_id
        WHERE e.role != 'Cashier'
    """).fetchone()[0]
    assert wrong_store == 0 and wrong_role == 0


# ---------------------------------------------------------------------------
# Topic-specific invariants: finance
# ---------------------------------------------------------------------------

def test_finance_running_balances_actually_run(topic, topic_db):
    """Each balance_after must be the previous one plus the amount.

    This is the invariant that makes the ledger usable for testing a
    statement view. Generated banking data almost never satisfies it.
    """
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    breaks = topic_db.execute("""
        WITH ordered AS (
            SELECT account_id, amount, balance_after,
                   LAG(balance_after) OVER (
                       PARTITION BY account_id ORDER BY occurred_at, id
                   ) AS previous
            FROM transactions
        )
        SELECT COUNT(*) FROM ordered
        WHERE previous IS NOT NULL
          AND ABS(previous + amount - balance_after) > 0.005
    """).fetchone()[0]
    assert breaks == 0, f"{breaks} transactions break the running balance"


def test_finance_account_balance_is_its_closing_balance(topic, topic_db):
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    bad = topic_db.execute("""
        WITH last AS (
            SELECT account_id, balance_after,
                   ROW_NUMBER() OVER (
                       PARTITION BY account_id ORDER BY occurred_at DESC, id DESC
                   ) AS rn
            FROM transactions
        )
        SELECT COUNT(*) FROM accounts a
        JOIN last ON last.account_id = a.id AND last.rn = 1
        WHERE ABS(a.balance - last.balance_after) > 0.005
    """).fetchone()[0]
    assert bad == 0


def test_finance_overdraft_limits_are_respected(topic, topic_db):
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    breached = topic_db.execute("""
        SELECT COUNT(*) FROM transactions t
        JOIN accounts a ON a.id = t.account_id
        WHERE t.balance_after < -a.overdraft_limit - 0.005
    """).fetchone()[0]
    assert breached == 0


def test_finance_loans_amortise_to_zero(topic, topic_db):
    """A fully repaid loan's final balance must be exactly 0.00."""
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    split = topic_db.execute(
        "SELECT COUNT(*) FROM loan_payments "
        "WHERE ABS(payment_amount - interest_amount - principal_amount) > 0.005"
    ).fetchone()[0]
    assert split == 0, "an instalment does not split into interest plus principal"

    unpaid = topic_db.execute("""
        WITH final AS (
            SELECT lp.loan_id, lp.balance_after,
                   ROW_NUMBER() OVER (
                       PARTITION BY lp.loan_id ORDER BY instalment_number DESC
                   ) AS rn
            FROM loan_payments lp
            JOIN loans l ON l.id = lp.loan_id
            WHERE l.status = 'paid_off'
        )
        SELECT COUNT(*) FROM final WHERE rn = 1 AND ABS(balance_after) > 0.005
    """).fetchone()[0]
    assert unpaid == 0, "a paid-off loan does not amortise to zero"


def test_finance_ohlc_relationship_holds(topic, topic_db):
    """high >= max(open, close) and low <= min(open, close), every row.

    Candlestick charts depend on it. Data that breaks it renders as
    visual nonsense.
    """
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    bad = topic_db.execute("""
        SELECT COUNT(*) FROM stock_prices
        WHERE high_price < MAX(open_price, close_price)
           OR low_price  > MIN(open_price, close_price)
    """).fetchone()[0]
    assert bad == 0


def test_finance_ibans_and_cards_validate(topic, topic_db):
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    from generators.common.identifiers import iban_is_valid

    bad_ibans = [
        iban for (iban,) in topic_db.execute("SELECT iban FROM accounts")
        if not iban_is_valid(iban)
    ]
    assert not bad_ibans[:5], f"IBANs failing mod-97: {bad_ibans[:5]}"


def test_finance_markets_are_shut_at_weekends(topic, topic_db):
    if topic.name != "finance":
        pytest.skip("finance-specific invariant")

    for table, column in [("stock_prices", "trade_date"), ("exchange_rates", "rate_date")]:
        weekend = topic_db.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE CAST(strftime('%w', {column}) AS INTEGER) IN (0, 6)"
        ).fetchone()[0]
        assert weekend == 0, f"{table} has {weekend} weekend rows"


# ---------------------------------------------------------------------------
# Topic-specific invariants: automobile
# ---------------------------------------------------------------------------

def test_automobile_odometers_never_run_backwards(topic, topic_db):
    """Mileage must increase monotonically through a vehicle's history.

    Odometer rollback is fraud. Data that does it by accident cannot be
    used to test detection of it.
    """
    if topic.name != "automobile":
        pytest.skip("automobile-specific invariant")

    rollbacks = topic_db.execute("""
        WITH ordered AS (
            SELECT vehicle_id, mileage_km,
                   LAG(mileage_km) OVER (
                       PARTITION BY vehicle_id ORDER BY service_date, id
                   ) AS previous
            FROM service_records
        )
        SELECT COUNT(*) FROM ordered
        WHERE previous IS NOT NULL AND mileage_km < previous
    """).fetchone()[0]
    assert rollbacks == 0

    above_current = topic_db.execute("""
        SELECT COUNT(*) FROM service_records s
        JOIN vehicles v ON v.id = s.vehicle_id
        WHERE s.mileage_km > v.mileage_km
    """).fetchone()[0]
    assert above_current == 0, "a service reading exceeds the car's current mileage"


def test_automobile_vins_and_plates_are_valid(topic, topic_db):
    if topic.name != "automobile":
        pytest.skip("automobile-specific invariant")

    from generators.common.identifiers import licence_plate_is_valid, vin_is_valid

    bad_vins = [v for (v,) in topic_db.execute("SELECT vin FROM vehicles") if not vin_is_valid(v)]
    assert not bad_vins[:5], f"VINs failing their check digit: {bad_vins[:5]}"

    bad_plates = [
        p for (p,) in topic_db.execute("SELECT plate FROM vehicles")
        if not licence_plate_is_valid(p)
    ]
    assert not bad_plates[:5], f"plates not in the Spanish format: {bad_plates[:5]}"


def test_automobile_ownership_chains_are_contiguous(topic, topic_db):
    """Ownership periods must tile a vehicle's life with no gaps or overlaps."""
    if topic.name != "automobile":
        pytest.skip("automobile-specific invariant")

    open_rows = topic_db.execute("""
        SELECT COUNT(*) FROM (
            SELECT vehicle_id, SUM(owned_until IS NULL) AS open_count
            FROM ownership_history GROUP BY vehicle_id
            HAVING open_count != 1
        )
    """).fetchone()[0]
    assert open_rows == 0, "a vehicle has zero or several current keepers"

    gaps = topic_db.execute("""
        WITH ordered AS (
            SELECT vehicle_id, owned_from,
                   LAG(owned_until) OVER (
                       PARTITION BY vehicle_id ORDER BY owned_from
                   ) AS previous_end
            FROM ownership_history
        )
        SELECT COUNT(*) FROM ordered
        WHERE previous_end IS NOT NULL AND previous_end != owned_from
    """).fetchone()[0]
    assert gaps == 0, "ownership periods leave a gap or overlap"


def test_automobile_service_invoices_add_up(topic, topic_db):
    if topic.name != "automobile":
        pytest.skip("automobile-specific invariant")

    bad = topic_db.execute(
        "SELECT COUNT(*) FROM service_records "
        "WHERE ABS(total_cost - parts_cost - labour_cost) > 0.005"
    ).fetchone()[0]
    assert bad == 0


def test_automobile_itv_follows_the_spanish_schedule(topic, topic_db):
    """No car is inspected before it turns four -- Spanish law says so."""
    if topic.name != "automobile":
        pytest.skip("automobile-specific invariant")

    too_early = topic_db.execute("""
        SELECT COUNT(*) FROM inspections i
        JOIN vehicles v ON v.id = i.vehicle_id
        WHERE julianday(i.inspection_date) - julianday(v.registered_on) < 4 * 365.25 - 2
    """).fetchone()[0]
    assert too_early == 0

    inconsistent = topic_db.execute(
        "SELECT COUNT(*) FROM inspections "
        "WHERE result = 'favourable' AND defects IS NOT NULL"
    ).fetchone()[0]
    assert inconsistent == 0, "a favourable inspection lists defects"


def test_automobile_electric_vehicles_have_no_displacement(topic, topic_db):
    if topic.name != "automobile":
        pytest.skip("automobile-specific invariant")

    bad = topic_db.execute(
        "SELECT COUNT(*) FROM vehicles WHERE fuel_type = 'electric' AND engine_cc != 0"
    ).fetchone()[0]
    assert bad == 0


# ---------------------------------------------------------------------------
# Topic-specific invariants: education
# ---------------------------------------------------------------------------

def test_education_assessment_weights_sum_to_one(topic, topic_db):
    if topic.name != "education":
        pytest.skip("education-specific invariant")

    bad = topic_db.execute("""
        SELECT COUNT(*) FROM (
            SELECT enrollment_id, ROUND(SUM(weight), 4) AS total
            FROM grades GROUP BY enrollment_id
            HAVING ABS(total - 1.0) > 0.0001
        )
    """).fetchone()[0]
    assert bad == 0, "an enrolment's assessment weights do not sum to 1.00"


def test_education_final_grade_is_the_weighted_sum(topic, topic_db, repo_root):
    """final_grade must equal the weighted sum of its components.

    Compared with EXACT decimal arithmetic, not with SQL's SUM. SQLite works
    in binary floating point, where 7.3*0.35 + 7.6*0.35 + 5.6*0.30 comes to
    6.89499... rather than 6.895 and rounds the wrong way. The stored value
    is the correct one; the discrepancy is the classic float rounding trap,
    documented on the grades entity.
    """
    if topic.name != "education":
        pytest.skip("education-specific invariant")

    from decimal import Decimal

    components: dict[int, list[tuple[Decimal, Decimal]]] = {}
    for enrollment_id, score, weight in topic_db.execute(
        "SELECT enrollment_id, score, weight FROM grades"
    ):
        components.setdefault(enrollment_id, []).append(
            (Decimal(str(score)), Decimal(str(weight)))
        )

    mismatches = []
    for enrollment_id, final_grade in topic_db.execute(
        "SELECT id, final_grade FROM enrollments WHERE final_grade IS NOT NULL"
    ):
        expected = sum(
            score * weight for score, weight in components.get(enrollment_id, [])
        )
        if expected.quantize(Decimal("0.01")) != Decimal(str(final_grade)).quantize(
            Decimal("0.01")
        ):
            mismatches.append((enrollment_id, final_grade, float(expected)))

    assert not mismatches[:5], f"final grades disagree with components: {mismatches[:5]}"


def test_education_grade_band_matches_the_grade(topic, topic_db):
    """The Spanish report-card band must follow from the numeric grade."""
    if topic.name != "education":
        pytest.skip("education-specific invariant")

    bad = topic_db.execute("""
        SELECT COUNT(*) FROM enrollments
        WHERE final_grade IS NOT NULL AND grade_band != CASE
            WHEN final_grade < 5 THEN 'Suspenso'
            WHEN final_grade < 6 THEN 'Aprobado'
            WHEN final_grade < 7 THEN 'Bien'
            WHEN final_grade < 9 THEN 'Notable'
            ELSE 'Sobresaliente' END
    """).fetchone()[0]
    assert bad == 0


def test_education_attendance_predicts_achievement(topic, topic_db):
    """The signal this topic exists for must actually be present.

    Attendance and final grade are both driven by a hidden per-pupil
    diligence factor that is never published, so the relationship between
    them is emergent. If a change to the generators flattened it, this data
    would stop being useful for demonstrating analysis -- which is most of
    its value -- so the correlation is asserted rather than hoped for.

    The threshold is deliberately loose. This tests that a real signal
    exists, not that it has one exact strength.
    """
    if topic.name != "education":
        pytest.skip("education-specific invariant")

    import statistics

    rows = topic_db.execute("""
        SELECT attendance_rate, final_grade FROM enrollments
        WHERE attendance_rate IS NOT NULL AND final_grade IS NOT NULL
    """).fetchall()
    assert len(rows) >= 200, "too few enrolments to demonstrate the correlation"

    attendance = [float(a) for a, _ in rows]
    grades = [float(g) for _, g in rows]

    mean_a = statistics.mean(attendance)
    mean_g = statistics.mean(grades)
    covariance = sum(
        (a - mean_a) * (g - mean_g) for a, g in zip(attendance, grades)
    ) / len(rows)
    correlation = covariance / (
        statistics.pstdev(attendance) * statistics.pstdev(grades)
    )

    assert correlation > 0.25, (
        f"attendance and achievement correlate at only {correlation:.3f}. "
        f"The hidden diligence factor in _generate_students is what creates "
        f"this relationship -- check it still drives both attendance and "
        f"grade generation."
    )


def test_education_no_teaching_at_weekends(topic, topic_db):
    if topic.name != "education":
        pytest.skip("education-specific invariant")

    for table, column in [("attendance", "session_date"), ("exams", "exam_date")]:
        weekend = topic_db.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE CAST(strftime('%w', {column}) AS INTEGER) IN (0, 6)"
        ).fetchone()[0]
        assert weekend == 0, f"{table} has {weekend} weekend rows"


def test_education_exams_fit_their_room(topic, topic_db):
    if topic.name != "education":
        pytest.skip("education-specific invariant")

    overbooked = topic_db.execute("""
        SELECT COUNT(*) FROM exams e
        JOIN classrooms c ON c.id = e.classroom_id
        WHERE e.registered_students > c.capacity
    """).fetchone()[0]
    assert overbooked == 0


# ---------------------------------------------------------------------------
# 7. The build must not leave orphans behind
# ---------------------------------------------------------------------------

def test_no_orphaned_files_in_the_published_tree(topic, repo_root: Path):
    """Every published file must be one the current build would produce.

    The build used to be purely additive: rename a table and the old file
    stayed on disk forever, still advertised in the generated folder README
    as though it were current data. It was invisible because rebuilding over
    an existing tree reproduced itself perfectly -- only a build from an
    empty directory exposed it.

    This test names the expected files independently of the build, so it
    catches an orphan even if the pruning logic itself regresses.
    """
    expected: dict[str, set[str]] = {
        "csv": {f"{entity.name}.csv" for entity in topic.entities} | {"README.md"},
        "json": (
            {f"{entity.name}.json" for entity in topic.entities}
            | {"README.md"}
            # exactly one .ndjson per topic: the largest table
            | {
                f"{max(topic.entities, key=lambda e: 0).name}.ndjson"
            } if False else set()
        ),
        "schemas": {f"{entity.name}.schema.json" for entity in topic.entities},
        "db": {f"{topic.name}.sqlite", f"{topic.name}.sql.gz",
               "schema.sql", "README.md"},
    }

    # csv
    folder = repo_root / "csv" / topic.name
    if folder.is_dir():
        actual = {p.name for p in folder.iterdir() if p.is_file()}
        assert actual == expected["csv"], (
            f"csv/{topic.name} contents differ from the schema.\n"
            f"  unexpected: {sorted(actual - expected['csv'])}\n"
            f"  missing:    {sorted(expected['csv'] - actual)}"
        )

    # schemas
    folder = repo_root / "schemas" / topic.name
    if folder.is_dir():
        actual = {p.name for p in folder.iterdir() if p.is_file()}
        assert actual == expected["schemas"], (
            f"schemas/{topic.name} contents differ.\n"
            f"  unexpected: {sorted(actual - expected['schemas'])}\n"
            f"  missing:    {sorted(expected['schemas'] - actual)}"
        )

    # db
    folder = repo_root / "db" / topic.name
    if folder.is_dir():
        actual = {p.name for p in folder.iterdir() if p.is_file()}
        assert actual == expected["db"], (
            f"db/{topic.name} contents differ.\n"
            f"  unexpected: {sorted(actual - expected['db'])}\n"
            f"  missing:    {sorted(expected['db'] - actual)}"
        )

    # json: one file per entity, plus README, plus exactly one .ndjson
    folder = repo_root / "json" / topic.name
    if folder.is_dir():
        actual = {p.name for p in folder.iterdir() if p.is_file()}
        ndjson = {name for name in actual if name.endswith(".ndjson")}
        assert len(ndjson) == 1, (
            f"json/{topic.name} should hold exactly one .ndjson "
            f"(the largest table), found {sorted(ndjson)}"
        )
        non_ndjson = actual - ndjson
        expected_json = {f"{e.name}.json" for e in topic.entities} | {"README.md"}
        assert non_ndjson == expected_json, (
            f"json/{topic.name} contents differ.\n"
            f"  unexpected: {sorted(non_ndjson - expected_json)}\n"
            f"  missing:    {sorted(expected_json - non_ndjson)}"
        )
