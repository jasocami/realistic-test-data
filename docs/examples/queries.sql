-- ===========================================================================
-- Worked SQL queries against the clinical database.
--
--     sqlite3 db/clinical/clinical.sqlite < docs/examples/queries.sql
--
-- Every query here runs as written. They are ordered from simplest to most
-- involved, and each one demonstrates something specific about the data.
-- ===========================================================================

-- Enforce the foreign keys. SQLite ignores them otherwise -- and this is a
-- property of the CONNECTION, so it has to be set every time you connect.
PRAGMA foreign_keys = ON;

.headers on
.mode column


-- ---------------------------------------------------------------------------
-- 1. What is in here?
-- ---------------------------------------------------------------------------
SELECT 'hospitals' AS table_name, COUNT(*) AS rows FROM hospitals
UNION ALL SELECT 'doctors',       COUNT(*) FROM doctors
UNION ALL SELECT 'patients',      COUNT(*) FROM patients
UNION ALL SELECT 'appointments',  COUNT(*) FROM appointments
UNION ALL SELECT 'lab_results',   COUNT(*) FROM lab_results;


-- ---------------------------------------------------------------------------
-- 2. Follow one patient across five tables.
--    Note the LEFT JOIN: not every appointment produces a diagnosis, and an
--    inner join would silently drop those rows.
-- ---------------------------------------------------------------------------
SELECT p.mrn,
       substr(a.scheduled_at, 1, 10) AS on_date,
       a.status,
       d.full_name  AS doctor,
       dx.icd10_code
FROM patients p
JOIN appointments a ON a.patient_id = p.id
JOIN doctors      d ON d.id = a.doctor_id
LEFT JOIN diagnoses dx ON dx.appointment_id = a.id
WHERE p.mrn = 'MRN-0000004'
ORDER BY a.scheduled_at
LIMIT 5;


-- ---------------------------------------------------------------------------
-- 3. The patients with no insurance policy -- about 10% of them, on purpose,
--    so a LEFT JOIN has something to miss.
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS uninsured_patients
FROM patients p
LEFT JOIN insurance_policies i ON i.patient_id = p.id
WHERE i.id IS NULL;


-- ---------------------------------------------------------------------------
-- 4. Lab results outside their reference range.
--    `flag` is derivable from the other three columns -- recompute it and
--    check you agree. (You will; it is enforced in CI.)
-- ---------------------------------------------------------------------------
SELECT test_name,
       COUNT(*)                                   AS results,
       SUM(flag = 'HIGH')                         AS high,
       SUM(flag = 'LOW')                          AS low,
       ROUND(100.0 * SUM(flag != 'NORMAL') / COUNT(*), 1) AS pct_abnormal
FROM lab_results
GROUP BY test_name
ORDER BY pct_abnormal DESC
LIMIT 8;


-- ---------------------------------------------------------------------------
-- 5. Does HbA1c really rise with age? This is the correlation that makes the
--    lab data worth plotting rather than just parsing.
-- ---------------------------------------------------------------------------
SELECT CASE
         WHEN age < 35 THEN 'under 35'
         WHEN age < 55 THEN '35-54'
         WHEN age < 70 THEN '55-69'
         ELSE '70+'
       END                          AS age_band,
       COUNT(*)                     AS results,
       ROUND(AVG(value), 2)         AS mean_hba1c
FROM (
    SELECT l.value,
           (2025 - CAST(substr(p.date_of_birth, 1, 4) AS INTEGER)) AS age
    FROM lab_results l
    JOIN patients p ON p.id = l.patient_id
    WHERE l.test_name = 'Haemoglobin A1c'
)
GROUP BY age_band
ORDER BY mean_hba1c;


-- ---------------------------------------------------------------------------
-- 6. The most common diagnoses, with their real ICD-10 codes.
-- ---------------------------------------------------------------------------
SELECT icd10_code, description, COUNT(*) AS times_recorded
FROM diagnoses
GROUP BY icd10_code, description
ORDER BY times_recorded DESC
LIMIT 8;


-- ---------------------------------------------------------------------------
-- 7. Busiest clinic hours. Plot this and you get the double hump of a real
--    outpatient day, with the lunchtime dip.
-- ---------------------------------------------------------------------------
SELECT strftime('%H:00', scheduled_at) AS hour,
       COUNT(*)                        AS appointments
FROM appointments
GROUP BY hour
ORDER BY hour;


-- ---------------------------------------------------------------------------
-- 8. Prove the integrity claim: every foreign key resolves.
--    An empty result is the whole point.
-- ---------------------------------------------------------------------------
PRAGMA foreign_key_check;
