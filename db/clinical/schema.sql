-- clinical/schema.sql
-- Table structure for the 'clinical' topic. No data -- see
-- clinical.sql.gz for the rows, or clinical.sqlite for a
-- database you can query immediately.
--
-- SYNTHETIC DATA -- every record is invented. See README.md.

PRAGMA foreign_keys = ON;

-- hospitals: One row per hospital site.
CREATE TABLE "hospitals" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL UNIQUE,
    "type" TEXT NOT NULL CHECK ("type" IN ('Children''s', 'Community', 'General', 'Specialist', 'Teaching')),
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "address" TEXT NOT NULL,
    "postal_code" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "beds" INTEGER NOT NULL,
    "founded" INTEGER NOT NULL
);

-- departments: One row per clinical department within one hospital.
CREATE TABLE "departments" (
    "id" INTEGER PRIMARY KEY,
    "hospital_id" INTEGER NOT NULL,
    "name" TEXT NOT NULL CHECK ("name" IN ('Cardiology', 'Dermatology', 'Emergency', 'General Surgery', 'Internal Medicine', 'Neurology', 'Obstetrics & Gynaecology', 'Oncology', 'Orthopaedics', 'Paediatrics', 'Psychiatry', 'Radiology')),
    "floor" INTEGER NOT NULL,
    "phone_extension" TEXT NOT NULL,
    FOREIGN KEY ("hospital_id") REFERENCES "hospitals" ("id")
);
CREATE INDEX "idx_departments_hospital_id" ON "departments" ("hospital_id");

-- doctors: One row per doctor practising at one hospital.
CREATE TABLE "doctors" (
    "id" INTEGER PRIMARY KEY,
    "hospital_id" INTEGER NOT NULL,
    "department_id" INTEGER NOT NULL,
    "full_name" TEXT NOT NULL,
    "specialty" TEXT NOT NULL,
    "license_number" TEXT NOT NULL UNIQUE,
    "email" TEXT NOT NULL,
    "hired_at" TEXT NOT NULL,
    "qualification" TEXT NOT NULL CHECK ("qualification" IN ('Lic. Medicina', 'Grado en Medicina', 'Dr. en Medicina', 'Lic. Medicina, Esp. vía MIR', 'Grado en Medicina, Esp. vía MIR', 'Dr. en Medicina, Esp. vía MIR')),
    FOREIGN KEY ("hospital_id") REFERENCES "hospitals" ("id"),
    FOREIGN KEY ("department_id") REFERENCES "departments" ("id")
);
CREATE INDEX "idx_doctors_hospital_id" ON "doctors" ("hospital_id");
CREATE INDEX "idx_doctors_department_id" ON "doctors" ("department_id");

-- patients: One row per person registered in this dataset.
CREATE TABLE "patients" (
    "id" INTEGER PRIMARY KEY,
    "mrn" TEXT NOT NULL UNIQUE,
    "full_name" TEXT NOT NULL,
    "date_of_birth" TEXT NOT NULL,
    "sex" TEXT NOT NULL CHECK ("sex" IN ('F', 'M')),
    "blood_type" TEXT NOT NULL CHECK ("blood_type" IN ('A+', 'A-', 'AB+', 'AB-', 'B+', 'B-', 'O+', 'O-')),
    "phone" TEXT,
    "email" TEXT,
    "address" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "postal_code" TEXT NOT NULL,
    "registered_at" TEXT NOT NULL
);

-- insurance_policies: One row per insurance policy held by one patient.
CREATE TABLE "insurance_policies" (
    "id" INTEGER PRIMARY KEY,
    "patient_id" INTEGER NOT NULL UNIQUE,
    "provider" TEXT NOT NULL CHECK ("provider" IN ('Arcadia Health Plan', 'Blue Harbour Cover', 'Caldera Care', 'Lakeview Assurance', 'Meridian Mutual', 'Northwind Health', 'Pinefield Medical', 'Stonebridge Health')),
    "policy_number" TEXT NOT NULL UNIQUE,
    "coverage_level" TEXT NOT NULL CHECK ("coverage_level" IN ('Basic', 'Comprehensive', 'Premium', 'Standard')),
    "annual_premium" REAL NOT NULL,
    "valid_from" TEXT NOT NULL,
    "valid_until" TEXT NOT NULL,
    FOREIGN KEY ("patient_id") REFERENCES "patients" ("id")
);
CREATE INDEX "idx_insurance_policies_patient_id" ON "insurance_policies" ("patient_id");

-- appointments: One row per booked appointment between a patient and a doctor.
CREATE TABLE "appointments" (
    "id" INTEGER PRIMARY KEY,
    "patient_id" INTEGER NOT NULL,
    "doctor_id" INTEGER NOT NULL,
    "hospital_id" INTEGER NOT NULL,
    "scheduled_at" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL,
    "status" TEXT NOT NULL CHECK ("status" IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    "reason" TEXT NOT NULL CHECK ("reason" IN ('Acute symptoms', 'Annual screening', 'Follow-up consultation', 'Medication review', 'New referral', 'Post-operative review', 'Pre-operative assessment', 'Routine check-up', 'Second opinion', 'Test results discussion')),
    "notes" TEXT,
    FOREIGN KEY ("patient_id") REFERENCES "patients" ("id"),
    FOREIGN KEY ("doctor_id") REFERENCES "doctors" ("id"),
    FOREIGN KEY ("hospital_id") REFERENCES "hospitals" ("id")
);
CREATE INDEX "idx_appointments_patient_id" ON "appointments" ("patient_id");
CREATE INDEX "idx_appointments_doctor_id" ON "appointments" ("doctor_id");
CREATE INDEX "idx_appointments_hospital_id" ON "appointments" ("hospital_id");

-- diagnoses: One row per diagnosis recorded at one completed appointment.
CREATE TABLE "diagnoses" (
    "id" INTEGER PRIMARY KEY,
    "patient_id" INTEGER NOT NULL,
    "appointment_id" INTEGER NOT NULL,
    "icd10_code" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "severity" TEXT NOT NULL CHECK ("severity" IN ('mild', 'moderate', 'severe')),
    "diagnosed_at" TEXT NOT NULL,
    "is_chronic" INTEGER NOT NULL,
    FOREIGN KEY ("patient_id") REFERENCES "patients" ("id"),
    FOREIGN KEY ("appointment_id") REFERENCES "appointments" ("id")
);
CREATE INDEX "idx_diagnoses_patient_id" ON "diagnoses" ("patient_id");
CREATE INDEX "idx_diagnoses_appointment_id" ON "diagnoses" ("appointment_id");

-- prescriptions: One row per medication prescribed to one patient by one doctor.
CREATE TABLE "prescriptions" (
    "id" INTEGER PRIMARY KEY,
    "patient_id" INTEGER NOT NULL,
    "doctor_id" INTEGER NOT NULL,
    "medication" TEXT NOT NULL,
    "dosage" TEXT NOT NULL,
    "frequency" TEXT NOT NULL,
    "start_date" TEXT NOT NULL,
    "end_date" TEXT,
    "refills_allowed" INTEGER NOT NULL,
    FOREIGN KEY ("patient_id") REFERENCES "patients" ("id"),
    FOREIGN KEY ("doctor_id") REFERENCES "doctors" ("id")
);
CREATE INDEX "idx_prescriptions_patient_id" ON "prescriptions" ("patient_id");
CREATE INDEX "idx_prescriptions_doctor_id" ON "prescriptions" ("doctor_id");

-- lab_results: One row per individual laboratory measurement.
CREATE TABLE "lab_results" (
    "id" INTEGER PRIMARY KEY,
    "patient_id" INTEGER NOT NULL,
    "loinc_code" TEXT NOT NULL,
    "test_name" TEXT NOT NULL,
    "value" REAL NOT NULL,
    "unit" TEXT NOT NULL,
    "reference_low" REAL NOT NULL,
    "reference_high" REAL NOT NULL,
    "flag" TEXT NOT NULL CHECK ("flag" IN ('LOW', 'NORMAL', 'HIGH')),
    "collected_at" TEXT NOT NULL,
    FOREIGN KEY ("patient_id") REFERENCES "patients" ("id")
);
CREATE INDEX "idx_lab_results_patient_id" ON "lab_results" ("patient_id");
