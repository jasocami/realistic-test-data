"""
Query the SQLite database, including the pragma everybody forgets.

    python docs/examples/05_query_sqlite.py
"""

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATABASE = REPO_ROOT / "db" / "clinical" / "clinical.sqlite"


def main() -> None:
    connection = sqlite3.connect(DATABASE)

    # THE ONE EVERYBODY FORGETS.
    #
    # SQLite accepts FOREIGN KEY syntax and then ignores it unless you turn
    # this on -- and it is per CONNECTION, not per file. Open the database
    # again tomorrow and you have to set it again.
    connection.execute("PRAGMA foreign_keys = ON;")

    # Rows behave like dicts, so you can use column names.
    connection.row_factory = sqlite3.Row

    print("Five tables joined, following one patient:\n")
    rows = connection.execute("""
        SELECT p.mrn, p.full_name,
               a.scheduled_at, a.status,
               d.full_name AS doctor,
               h.name      AS hospital,
               dx.icd10_code, dx.description
        FROM patients p
        JOIN appointments a ON a.patient_id = p.id
        JOIN doctors      d ON d.id = a.doctor_id
        JOIN hospitals    h ON h.id = a.hospital_id
        LEFT JOIN diagnoses dx ON dx.appointment_id = a.id
        WHERE p.mrn = 'MRN-0000004'
        ORDER BY a.scheduled_at
        LIMIT 4
    """).fetchall()

    for row in rows:
        diagnosis = row["description"] or "— no diagnosis recorded"
        print(f"  {row['scheduled_at'][:10]}  {row['status']:<10} "
              f"{row['doctor']:<26} {diagnosis[:44]}")

    # The LEFT JOIN above matters: not every appointment produces a
    # diagnosis. Use an inner join and you silently lose rows.
    total, with_diagnosis = connection.execute("""
        SELECT COUNT(*),
               SUM(EXISTS (SELECT 1 FROM diagnoses dx
                           WHERE dx.appointment_id = a.id))
        FROM appointments a
    """).fetchone()
    print(f"\n{with_diagnosis:,} of {total:,} appointments have a diagnosis. "
          f"An INNER JOIN would drop the other {total - with_diagnosis:,}.")

    connection.close()


if __name__ == "__main__":
    main()
