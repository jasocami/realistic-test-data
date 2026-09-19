"""
Topic: clinical -- hospitals, patients, appointments, diagnoses, lab results.
===============================================================================

READ THIS FILE FIRST.
---------------------
This is the *reference implementation* for the repository. Every other topic
follows the same shape, so if you understand this file you understand all of
them. It is deliberately over-commented for that reason.

A topic module has exactly three parts, in this order:

    PART 1  Reference data   -- the real-world vocabularies we draw from
                                (ICD-10 codes, lab tests, specialties)
    PART 2  The schema       -- one Entity per table, fully documented
    PART 3  The generator    -- a function that produces the rows

...and then a `TOPIC` object at the bottom tying the entities together.

To add your own topic, copy this file and work through the three parts.
docs/generators/adding-a-topic.md walks through it step by step.

WHAT MAKES THIS DATA "REALISTIC"?
---------------------------------
Not the names -- anyone can generate names. Three things:

1. **The references resolve.** Every appointment points at a patient who
   exists and a doctor who exists, and that doctor actually works at the
   hospital the appointment is booked into. No orphans, no impossibilities.

2. **The distributions are lopsided.** Blood types follow their real-world
   frequencies. Ages follow a population pyramid. Appointment statuses are
   mostly "completed" with a realistic tail of no-shows. Uniform randomness
   is the single most obvious tell of fake data.

3. **The values correlate.** A 78-year-old's blood pressure and HbA1c differ
   from a 24-year-old's, because we generate them from age-adjusted
   distributions rather than independently. That means the data is actually
   usable for demonstrating analysis, not just for testing parsers.

IS ANY OF THIS REAL?
--------------------
No. Every patient, doctor and hospital is invented. What IS real is the
*coding systems* -- ICD-10 diagnosis codes and LOINC laboratory codes are
public international standards, not personal data, and using the genuine
codes is what lets you test a real terminology lookup. Contact details use
the reserved 555-01xx telephone range and example.com, neither of which can
reach a real person.
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Any

from ..common.dates import add_years, age_on, next_weekday
from ..common.geography import PROVINCES, generate_address, phone_number
from ..common.identifiers import business_key
from ..common.schema import Entity, Field, Topic
from ..common.seeds import Rng

# ===========================================================================
# PART 1 -- REFERENCE DATA
# ===========================================================================
# The real-world vocabularies this topic draws on. Keeping them at the top,
# as plain data, means you can see exactly what the generator can produce
# without reading any of the generation logic.

#: How many rows of each entity to produce by default.
#: Chosen so the whole topic stays a few megabytes -- big enough to be
#: interesting, small enough to clone in seconds. Override with
#: `python build.py --topic clinical --scale 10`.
DEFAULT_COUNTS = {
    "hospitals": 25,
    "departments": 120,
    "doctors": 250,
    "patients": 800,
    # NOT an independent number: keep this at roughly 90% of `patients`.
    # The table's documented purpose is that the remaining ~10% of patients
    # have NO policy, so there is something for a LEFT JOIN to miss. Set it
    # at or above `patients` and every patient becomes insured, which
    # silently destroys that test case.
    "insurance_policies": 720,
    "appointments": 3_500,
    "diagnoses": 2_200,
    "prescriptions": 2_800,
    "lab_results": 5_000,
}

#: The window every date in this topic falls inside. Fixed rather than
#: relative to "today", so the data does not silently change meaning as time
#: passes and so rebuilds stay reproducible.
PERIOD_START = date(2023, 1, 1)
PERIOD_END = date(2025, 12, 31)

#: The date the dataset is "as of". Appointments after this are still
#: scheduled; before it, they have happened. Also used to compute ages.
AS_OF = date(2025, 6, 30)

#: How far ahead the appointment book runs. Real outpatient clinics hold
#: roughly three to four months of forward bookings -- not the full period.
#: Without this cap the future would be over-represented, because the dataset
#: period extends well past AS_OF.
BOOKING_HORIZON_DAYS = 120

#: Cities too large to plausibly host a "Hospital Comarcal", which by
#: definition serves a rural comarca rather than a provincial capital.
MAJOR_CITIES = {
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza", "Málaga",
    "Murcia", "Palma", "Las Palmas de Gran Canaria", "Bilbao", "Alicante",
    "Córdoba", "Valladolid", "Vigo", "Granada", "Oviedo",
}

HOSPITAL_TYPES = {
    "General": 10,
    "Teaching": 4,
    "Community": 6,
    "Specialist": 3,
    "Children's": 2,
}

#: Clinical departments, with the specialties a doctor in that department
#: might hold. Keeping them paired is what stops the generator producing a
#: paediatrician working in the cardiology department.
DEPARTMENTS = {
    "Cardiology": ["Cardiology", "Interventional Cardiology", "Electrophysiology"],
    "Emergency": ["Emergency Medicine", "Trauma Surgery"],
    "Internal Medicine": ["Internal Medicine", "Geriatrics", "Endocrinology"],
    "Paediatrics": ["Paediatrics", "Neonatology"],
    "Orthopaedics": ["Orthopaedic Surgery", "Sports Medicine"],
    "Neurology": ["Neurology", "Neurosurgery"],
    "Oncology": ["Medical Oncology", "Radiation Oncology", "Haematology"],
    "Radiology": ["Diagnostic Radiology", "Interventional Radiology"],
    "Obstetrics & Gynaecology": ["Obstetrics", "Gynaecology"],
    "Dermatology": ["Dermatology"],
    "Psychiatry": ["Psychiatry", "Child Psychiatry"],
    "General Surgery": ["General Surgery", "Vascular Surgery"],
}

#: Real ICD-10 codes. ICD-10 is the World Health Organization's International
#: Classification of Diseases -- the standard vocabulary hospitals worldwide
#: use to record what is wrong with a patient. These are genuine codes, which
#: means you can look any of them up in a public ICD-10 browser and get the
#: same description you see here. That is what makes them useful for testing
#: a terminology integration.
#:
#: Format: (code, description, typical department, weight)
#: The weight makes common conditions common -- hypertension appears far more
#: often than a rare arrhythmia, as it does in a real hospital.
ICD10_CODES = [
    ("I10",    "Essential (primary) hypertension",                    "Cardiology",        90),
    ("E11.9",  "Type 2 diabetes mellitus without complications",      "Internal Medicine", 80),
    ("J06.9",  "Acute upper respiratory infection, unspecified",      "Emergency",         75),
    ("M54.5",  "Low back pain",                                       "Orthopaedics",      70),
    ("E78.5",  "Hyperlipidaemia, unspecified",                        "Internal Medicine", 65),
    ("K21.9",  "Gastro-oesophageal reflux disease without oesophagitis", "Internal Medicine", 55),
    ("F41.1",  "Generalized anxiety disorder",                        "Psychiatry",        50),
    ("J45.909", "Unspecified asthma, uncomplicated",                  "Paediatrics",       48),
    ("N39.0",  "Urinary tract infection, site not specified",         "Emergency",         45),
    ("M17.9",  "Osteoarthritis of knee, unspecified",                 "Orthopaedics",      42),
    ("F32.9",  "Major depressive disorder, single episode",           "Psychiatry",        40),
    ("E03.9",  "Hypothyroidism, unspecified",                         "Internal Medicine", 38),
    ("I48.91", "Unspecified atrial fibrillation",                     "Cardiology",        35),
    ("J44.9",  "Chronic obstructive pulmonary disease, unspecified",  "Internal Medicine", 33),
    ("L20.9",  "Atopic dermatitis, unspecified",                      "Dermatology",       30),
    ("G43.909", "Migraine, unspecified, not intractable",             "Neurology",         28),
    ("S52.501", "Unspecified fracture of lower end of right radius",  "Orthopaedics",      25),
    ("D50.9",  "Iron deficiency anaemia, unspecified",                "Oncology",          24),
    ("I25.10", "Atherosclerotic heart disease of native coronary artery", "Cardiology",    22),
    ("N18.3",  "Chronic kidney disease, stage 3",                     "Internal Medicine", 20),
    ("G47.33", "Obstructive sleep apnoea",                            "Neurology",         18),
    ("K57.30", "Diverticulosis of large intestine without perforation", "General Surgery", 16),
    ("H25.9",  "Age-related cataract, unspecified",                   "General Surgery",   15),
    ("C50.911", "Malignant neoplasm of unspecified site of right breast", "Oncology",      12),
    ("I63.9",  "Cerebral infarction, unspecified",                    "Neurology",         10),
    ("O80",    "Encounter for full-term uncomplicated delivery",      "Obstetrics & Gynaecology", 30),
    ("Z00.00", "General adult medical examination without abnormal findings", "Internal Medicine", 60),
    ("R51.9",  "Headache, unspecified",                               "Emergency",         35),
    ("R10.9",  "Unspecified abdominal pain",                          "Emergency",         40),
    ("T78.40", "Allergy, unspecified",                                "Paediatrics",       26),
]

#: Real LOINC codes for common laboratory tests. LOINC is the international
#: standard for identifying lab observations -- "what test is this?" -- and
#: like ICD-10 it is a public code system, not patient data.
#:
#: Format: (loinc_code, test_name, unit, ref_low, ref_high, mean, sd, age_slope)
#:
#: `age_slope` is how much the mean shifts per year of patient age. It is
#: what makes an 80-year-old's results look different from a 20-year-old's,
#: which is the difference between data you can plot and data you can only
#: parse. Set to 0.0 for tests that do not drift with age.
LAB_TESTS = [
    # code       name                      unit      low    high   mean   sd    age_slope
    ("4548-4",  "Haemoglobin A1c",        "%",      4.0,   5.7,   5.4,   0.9,  0.012),
    ("2345-7",  "Glucose, fasting",       "mg/dL",  70.0,  99.0,  92.0,  16.0, 0.22),
    ("2093-3",  "Cholesterol, total",     "mg/dL",  0.0,   200.0, 186.0, 34.0, 0.40),
    ("2085-9",  "HDL cholesterol",        "mg/dL",  40.0,  200.0, 54.0,  14.0, -0.05),
    ("2089-1",  "LDL cholesterol",        "mg/dL",  0.0,   130.0, 112.0, 30.0, 0.30),
    ("2571-8",  "Triglycerides",          "mg/dL",  0.0,   150.0, 128.0, 55.0, 0.35),
    ("718-7",   "Haemoglobin",            "g/dL",   12.0,  17.5,  14.1,  1.5,  -0.010),
    ("789-8",   "Erythrocyte count",      "10*6/uL", 4.2,  5.9,   4.8,   0.5,  -0.003),
    ("6690-2",  "Leukocyte count",        "10*3/uL", 4.0,  11.0,  7.2,   2.0,  0.0),
    ("777-3",   "Platelet count",         "10*3/uL", 150.0, 400.0, 254.0, 60.0, -0.25),
    ("2160-0",  "Creatinine",             "mg/dL",  0.6,   1.3,   0.95,  0.24, 0.004),
    ("3094-0",  "Urea nitrogen",          "mg/dL",  7.0,   20.0,  14.5,  4.5,  0.06),
    ("1742-6",  "Alanine aminotransferase", "U/L",  7.0,   56.0,  27.0,  12.0, 0.0),
    ("1920-8",  "Aspartate aminotransferase", "U/L", 10.0, 40.0,  24.0,  9.0,  0.0),
    ("2951-2",  "Sodium",                 "mmol/L", 135.0, 145.0, 140.0, 2.5,  0.0),
    ("2823-3",  "Potassium",              "mmol/L", 3.5,   5.1,   4.2,   0.4,  0.0),
    ("3016-3",  "Thyrotropin (TSH)",      "mIU/L",  0.4,   4.0,   2.1,   1.1,  0.008),
    ("14682-9", "Creatinine, serum",      "umol/L", 53.0,  115.0, 84.0,  21.0, 0.35),
    ("1988-5",  "C-reactive protein",     "mg/L",   0.0,   5.0,   3.1,   4.0,  0.03),
    ("2276-4",  "Ferritin",               "ng/mL",  30.0,  400.0, 138.0, 85.0, 0.5),
]

#: Generic (non-brand) medication names with plausible dosages. Generic drug
#: names are public nomenclature -- no trademark issue, and they are what
#: appears on a real prescription anyway.
MEDICATIONS = [
    ("Lisinopril",      ["5 mg", "10 mg", "20 mg"],        "Once daily"),
    ("Metformin",       ["500 mg", "850 mg", "1000 mg"],   "Twice daily with meals"),
    ("Atorvastatin",    ["10 mg", "20 mg", "40 mg"],       "Once daily at night"),
    ("Amlodipine",      ["5 mg", "10 mg"],                 "Once daily"),
    ("Omeprazole",      ["20 mg", "40 mg"],                "Once daily before breakfast"),
    ("Levothyroxine",   ["50 mcg", "75 mcg", "100 mcg"],   "Once daily on an empty stomach"),
    ("Salbutamol",      ["100 mcg/dose"],                  "Two puffs as required"),
    ("Sertraline",      ["50 mg", "100 mg"],               "Once daily"),
    ("Amoxicillin",     ["250 mg", "500 mg"],              "Three times daily for 7 days"),
    ("Ibuprofen",       ["200 mg", "400 mg", "600 mg"],    "Three times daily after food"),
    ("Paracetamol",     ["500 mg", "1000 mg"],             "Up to four times daily"),
    ("Bisoprolol",      ["2.5 mg", "5 mg"],                "Once daily"),
    ("Ramipril",        ["2.5 mg", "5 mg", "10 mg"],       "Once daily"),
    ("Furosemide",      ["20 mg", "40 mg"],                "Once daily in the morning"),
    ("Gabapentin",      ["300 mg"],                        "Three times daily"),
    ("Apixaban",        ["2.5 mg", "5 mg"],                "Twice daily"),
    ("Prednisolone",    ["5 mg", "25 mg"],                 "Once daily, reducing course"),
    ("Cetirizine",      ["10 mg"],                         "Once daily"),
]

#: Blood group frequencies, as percentages of a broadly European population.
#: These add up to 100 and are close to published figures -- which is why a
#: histogram of this column looks like a real one.
BLOOD_TYPES = {
    "O+": 374, "A+": 357, "B+": 85, "AB+": 34,
    "O-": 66,  "A-": 63,  "B-": 15, "AB-": 6,
}

INSURANCE_PROVIDERS = [
    "Northwind Health", "Meridian Mutual", "Caldera Care", "Blue Harbour Cover",
    "Stonebridge Health", "Lakeview Assurance", "Pinefield Medical", "Arcadia Health Plan",
]

COVERAGE_LEVELS = {"Basic": 40, "Standard": 35, "Premium": 20, "Comprehensive": 5}

APPOINTMENT_REASONS = [
    "Routine check-up", "Follow-up consultation", "New referral",
    "Medication review", "Post-operative review", "Test results discussion",
    "Acute symptoms", "Annual screening", "Second opinion", "Pre-operative assessment",
]

#: Spanish medical qualifications. A doctor trained in Spain does not hold
#: an MBBS (British) or an MD/DO (American) -- they hold a Licenciatura or,
#: since the Bologna reform, a Grado en Medicina, and specialists qualify
#: through the MIR (Médico Interno Residente) competitive residency.
#:
#: Getting this wrong is the kind of error that is invisible to an English
#: reader and glaring to a Spanish one.
QUALIFICATIONS = [
    "Lic. Medicina",
    "Grado en Medicina",
    "Dr. en Medicina",
    "Lic. Medicina, Esp. vía MIR",
    "Grado en Medicina, Esp. vía MIR",
    "Dr. en Medicina, Esp. vía MIR",
]

#: The Bologna reform replaced the five-year Licenciatura with the six-year
#: Grado. Spanish medical faculties made the switch around 2010, with the
#: first Grado cohorts graduating from roughly 2016.
#:
#: So a doctor hired in 2004 CANNOT hold a Grado -- the degree did not exist
#: yet. Picking the qualification independently of the hire date produces
#: exactly that impossibility, which is why the two are generated together.
BOLOGNA_FIRST_GRADUATES = 2016

#: Qualifications available to someone who qualified before the reform.
PRE_BOLOGNA_QUALIFICATIONS = [
    "Lic. Medicina",
    "Dr. en Medicina",
    "Lic. Medicina, Esp. vía MIR",
    "Dr. en Medicina, Esp. vía MIR",
]

#: Qualifications available afterwards. Licenciatura holders are still
#: working -- and will be for decades -- so they remain in the pool, which is
#: why this list is the longer one.
POST_BOLOGNA_QUALIFICATIONS = [
    "Grado en Medicina",
    "Grado en Medicina, Esp. vía MIR",
    "Lic. Medicina",
    "Lic. Medicina, Esp. vía MIR",
    "Dr. en Medicina",
    "Dr. en Medicina, Esp. vía MIR",
]


# ===========================================================================
# PART 2 -- THE SCHEMA
# ===========================================================================
# One Entity per table. These definitions are the single source of truth:
# the CSV headers, the JSON Schemas, the SQLite CREATE TABLE statements, the
# ER diagram and the column dictionary in docs/topics/clinical.md are all
# generated from what is written below.
#
# Which is why every `description=` matters. It is not a comment for the next
# programmer -- it is the published documentation, and the build will refuse
# to run without it.

HOSPITALS = Entity(
    name="hospitals",
    topic="clinical",
    grain="One row per hospital site.",
    description=(
        "The physical sites in this dataset. Everything else in the clinical "
        "topic ultimately hangs off a hospital: departments belong to one, "
        "doctors work at one, and appointments take place at one."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. This is the "
                          "column everything else joins against."),
        Field("name", "string", unique=True,
              example="Hospital Universitario San Anselmo",
              description="The hospital's name, following real Spanish naming "
                          "conventions -- a religious dedication, the city it "
                          "serves, or a role descriptor such as Universitario "
                          "or Comarcal. The dedications are invented, so no "
                          "row names an existing institution."),
        Field("type", "enum", values=sorted(HOSPITAL_TYPES), example="General",
              description="What kind of hospital this is. Teaching hospitals are "
                          "attached to a medical school and tend to be larger; "
                          "Specialist sites cover a single discipline."),
        Field("city", "string", example="Sevilla",
              description="Spanish city the hospital is located in. These are "
                          "real municipalities, weighted by population, so "
                          "geocoding and mapping integrations work against "
                          "them."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())),
              example="Sevilla",
              description="The province the city belongs to. Always consistent "
                          "with the first two digits of the postal code, since "
                          "both are derived from the same choice of city."),
        Field("address", "string", example="Avenida de la Constitución, 47",
              description="Street address in Spanish format, with the number "
                          "after the street name. Invented -- the street and "
                          "number combination is not a real building."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41001",
              description="Spanish postal code. The first two digits are the "
                          "province code (28 Madrid, 08 Barcelona, 41 Sevilla), "
                          "so this always agrees with the province column."),
        Field("phone", "string", example="+34 954 21 08 33",
              description="Switchboard number in Spanish format. The dialling "
                          "prefix matches the province -- 91 Madrid, 93 "
                          "Barcelona, 954 Sevilla -- so the number agrees with "
                          "the address beside it."),
        Field("beds", "integer", unit="beds", example=420,
              description="Inpatient bed capacity, between 40 and 900 and "
                          "correlated with hospital type -- teaching hospitals "
                          "are the largest, community hospitals the smallest."),
        Field("founded", "integer", unit="year", example=1962,
              description="Calendar year the site first opened to patients, "
                          "spread between 1890 and 2015. Older sites tend to "
                          "be the larger General and Teaching hospitals."),
    ],
    notes=[
        "Bed counts correlate with `type`: Teaching hospitals average around "
        "700 beds, Community hospitals around 120. If you group by type and "
        "average the beds, you get a sensible-looking chart.",
    ],
)

DEPARTMENTS_ENTITY = Entity(
    name="departments",
    topic="clinical",
    grain="One row per clinical department within one hospital.",
    description=(
        "Departments divide a hospital into clinical specialties. The same "
        "department name appears at many hospitals -- 'Cardiology' exists at "
        "most of them -- so a department is identified by the pair "
        "(hospital_id, name), not by name alone."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("hospital_id", "integer", references="hospitals.id", example=1,
              description="The hospital this department belongs to. Every "
                          "department belongs to exactly one site."),
        Field("name", "enum", values=sorted(DEPARTMENTS), example="Cardiology",
              description="Department name, drawn from a fixed list of twelve "
                          "clinical specialties so that the same names recur "
                          "across hospitals and can be grouped."),
        Field("floor", "integer", example=3,
              description="Which floor of the building the department occupies, "
                          "from 0 (ground) to 8."),
        Field("phone_extension", "string", example="4417",
              description="Internal four-digit extension. Not dialable from "
                          "outside; this is the number staff would use."),
    ],
    notes=[
        "Not every hospital has every department. Smaller Community hospitals "
        "carry a handful; Teaching hospitals carry most of the list. This is "
        "why a naive cross join of hospitals and department names would give "
        "you more rows than exist here.",
    ],
)

DOCTORS = Entity(
    name="doctors",
    topic="clinical",
    grain="One row per doctor practising at one hospital.",
    description=(
        "Clinicians who see patients. Each doctor is attached to exactly one "
        "department at one hospital, and their specialty is always consistent "
        "with that department -- you will not find a paediatrician filed under "
        "Cardiology."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("hospital_id", "integer", references="hospitals.id", example=1,
              description="The hospital this doctor works at. Denormalised "
                          "alongside department_id on purpose, so you can filter "
                          "doctors by site without a second join -- and so there "
                          "is something to test a consistency check against."),
        Field("department_id", "integer", references="departments.id", example=1,
              description="The department this doctor works in. Always belongs "
                          "to the same hospital as hospital_id."),
        Field("full_name", "string", example="Dra. Lucía Fernández Ruiz",
              description="Display name including the Spanish title, which is "
                          "gendered: Dr. for men and Dra. for women. Spanish "
                          "people carry two surnames -- the father's then the "
                          "mother's -- which is worth testing any name parser "
                          "against."),
        Field("specialty", "string", example="Interventional Cardiology",
              description="The doctor's sub-specialty. Always one that belongs "
                          "to their department -- see the DEPARTMENTS table at "
                          "the top of generators/topics/clinical.py."),
        Field("license_number", "string", unique=True, pattern=r"^LIC-\d{7}$",
              example="LIC-0000042",
              description="Professional registration number. Invented format "
                          "that deliberately does not match any real medical "
                          "board's numbering scheme."),
        Field("email", "string", example="lucia.fernandez@example.org",
              description="Work email address, derived from the first name and "
                          "the first surname with accents transliterated away "
                          "(María becomes maria). Always on example.org, a "
                          "domain reserved by the IETF for documentation, so "
                          "nothing sent here could reach a real inbox."),
        Field("hired_at", "date", example="2016-09-01",
              description="Date the doctor joined this hospital. Always at least "
                          "25 years after their notional date of birth, so no "
                          "doctor in this dataset qualified as a child."),
        Field("qualification", "enum", values=QUALIFICATIONS,
              example="Lic. Medicina, Esp. vía MIR",
              description="Spanish medical credentials, consistent with the "
                          "hire date: Licenciatura for doctors who qualified "
                          "before the Bologna reform and Grado only for those "
                          "hired from 2016 onward, since the degree did not "
                          "exist before then. 'Esp. vía MIR' marks the "
                          "competitive specialty residency."),
    ],
)

PATIENTS = Entity(
    name="patients",
    topic="clinical",
    grain="One row per person registered in this dataset.",
    description=(
        "The anchor table of the clinical topic. Appointments, diagnoses, "
        "prescriptions, lab results and insurance policies all point back "
        "here. If you are exploring this topic for the first time, start with "
        "this table and follow the foreign keys outward."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=42,
              description="Surrogate primary key, sequential from 1. Use this "
                          "for joins."),
        Field("mrn", "string", unique=True, pattern=r"^MRN-\d{7}$",
              example="MRN-0000042",
              description="Medical Record Number -- the hospital's own permanent "
                          "identifier for a patient, and the number printed on a "
                          "wristband. Real hospitals identify patients by MRN "
                          "rather than by name, because names are ambiguous, "
                          "change, and are frequently misspelled."),
        Field("full_name", "string", example="María Fernández Ruiz",
              description="The patient's full name: given name, father's "
                          "surname, mother's surname, as Spanish names are "
                          "constructed. Invented; any resemblance to a real "
                          "person is coincidental and unavoidable given finite "
                          "name lists."),
        Field("date_of_birth", "date", example="1974-03-11",
              description="Date of birth in ISO-8601 format. Ages as of "
                          "2025-06-30 span 0 to 98 and follow a realistic "
                          "population pyramid, so there are many more "
                          "40-year-olds than 95-year-olds."),
        Field("sex", "enum", values=["F", "M"], example="F",
              description="Recorded biological sex, used here only because "
                          "several laboratory reference ranges differ by it. "
                          "Split roughly evenly."),
        Field("blood_type", "enum", values=sorted(BLOOD_TYPES), example="O+",
              description="ABO and Rh blood group, distributed by real-world "
                          "frequency: O+ is about 37% of rows and AB- under 1%. "
                          "A histogram of this column looks like a real one."),
        Field("phone", "string", nullable=True, example="+34 612 34 56 78",
              description="Contact telephone in Spanish format. About three "
                          "quarters are mobiles (6xx or 7xx, which carry no "
                          "geographic meaning); the rest are landlines whose "
                          "prefix matches the patient's province. Empty for "
                          "about 5% of patients, because real registration "
                          "data has gaps."),
        Field("email", "string", nullable=True,
              example="maria.fernandez@example.com",
              description="Contact email on the reserved example.com domain, "
                          "built from the given name and first surname with "
                          "accents stripped. Empty for about 12% of patients -- "
                          "older patients are noticeably more likely to have "
                          "none, as in reality."),
        Field("address", "string", example="Calle Mayor, 47, 3º B",
              description="Street address in Spanish format: street name first, "
                          "then the number, then an optional floor and door for "
                          "flats. Invented -- not a real dwelling."),
        Field("city", "string", example="Sevilla",
              description="Spanish city of residence, weighted by real "
                          "population. Not necessarily the same city as the "
                          "hospital the patient attends."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())),
              example="Sevilla",
              description="Province of residence. Always matches the first two "
                          "digits of the postal code, so address validation "
                          "that cross-checks the two will pass on this data."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41001",
              description="Spanish postal code, five digits. The leading pair "
                          "is the province code and runs from 01 (Álava) to 52 "
                          "(Melilla) -- codes like 00123 or 53001 do not exist "
                          "and are only found in the _edge-cases folders."),
        Field("registered_at", "date", example="2023-02-17",
              description="Date the patient was first registered at any hospital "
                          "in the dataset. Always on or before their first "
                          "appointment."),
    ],
    notes=[
        "Ages are drawn from a population pyramid rather than uniformly. That "
        "matters more than it sounds: age drives the laboratory results, so "
        "getting the age distribution right is what makes the lab data look "
        "clinically plausible when you plot it.",
        "Roughly 10% of patients have no insurance policy at all. They are the "
        "patients with no matching row in `insurance_policies` -- a deliberate "
        "LEFT JOIN test case.",
    ],
)

INSURANCE_POLICIES = Entity(
    name="insurance_policies",
    topic="clinical",
    grain="One row per insurance policy held by one patient.",
    description=(
        "Health insurance cover. Roughly 90% of patients hold exactly one "
        "policy and the remainder hold none, so this table is a natural test "
        "case for LEFT JOIN behaviour and for code that assumes every patient "
        "is insured."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("patient_id", "integer", references="patients.id", unique=True,
              example=42,
              description="The patient this policy covers. Unique, because in "
                          "this dataset a patient holds at most one policy."),
        Field("provider", "enum", values=sorted(INSURANCE_PROVIDERS),
              example="Northwind Health",
              description="Insurer name. All eight are invented companies; none "
                          "corresponds to a real insurance business."),
        Field("policy_number", "string", unique=True, pattern=r"^POL-\d{8}$",
              example="POL-00004217",
              description="The insurer's reference for this policy, as it would "
                          "be quoted on a claim."),
        Field("coverage_level", "enum", values=sorted(COVERAGE_LEVELS),
              example="Standard",
              description="Tier of cover, from Basic to Comprehensive. Weighted "
                          "towards the cheaper tiers, as real policy mixes are."),
        Field("annual_premium", "decimal", unit="USD", example=2480.00,
              description="What the policy costs per year. Correlates with "
                          "coverage level and with the patient's age, so a "
                          "scatter plot of premium against age slopes upward."),
        Field("valid_from", "date", example="2023-01-01",
              description="Date cover began. Always on or after the start of "
                          "the dataset period, 2023-01-01."),
        Field("valid_until", "date", example="2026-01-01",
              description="Date cover expires. Always after valid_from, "
                          "typically by one to three years."),
    ],
)

APPOINTMENTS = Entity(
    name="appointments",
    topic="clinical",
    grain="One row per booked appointment between a patient and a doctor.",
    description=(
        "The central activity table. Every appointment links a patient to a "
        "doctor at a hospital on a date. Appointments before 2025-06-30 have "
        "already happened and carry a final status; later ones are still "
        "scheduled."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("patient_id", "integer", references="patients.id", example=42,
              description="The patient the appointment is for. Never earlier "
                          "than that patient's registered_at date."),
        Field("doctor_id", "integer", references="doctors.id", example=17,
              description="Which clinician the patient is booked to see. "
                          "Determines the hospital column below, since an "
                          "appointment always takes place where that "
                          "clinician works."),
        Field("hospital_id", "integer", references="hospitals.id", example=1,
              description="Where the appointment takes place. Always the "
                          "hospital the doctor works at -- a consistency rule "
                          "the test suite checks explicitly."),
        Field("scheduled_at", "datetime", example="2024-06-14T09:30:00",
              description="Appointment date and time. Always on a weekday, "
                          "between 08:00 and 17:30, on a 15-minute boundary -- "
                          "because that is how clinic slots actually work."),
        Field("duration_minutes", "integer", unit="minutes", example=30,
              description="Slot length: 15, 20, 30, 45 or 60 minutes. New "
                          "referrals get longer slots than follow-ups."),
        Field("status", "enum",
              values=["scheduled", "completed", "cancelled", "no_show"],
              example="completed",
              description="Outcome. Past appointments are about 78% completed, "
                          "10% cancelled and 7% no-shows; future ones are always "
                          "'scheduled'. The no-show rate is deliberately "
                          "realistic -- it is a real operational problem and a "
                          "common thing to build a dashboard about."),
        Field("reason", "enum", values=sorted(APPOINTMENT_REASONS),
              example="Follow-up consultation",
              description="Why the appointment was booked, drawn from the ten "
                          "reasons that dominate real outpatient scheduling."),
        Field("notes", "text", nullable=True,
              example="Patient reports improvement since last review.",
              description="Free-text clinical note. Present on about 60% of "
                          "completed appointments and never on cancellations, "
                          "which makes this a good column for testing nullable "
                          "text handling and full-text search."),
    ],
    notes=[
        "`hospital_id` is intentionally derivable from `doctor_id`. It is "
        "stored anyway because real schemas denormalise for query speed, and "
        "because it gives you a genuine consistency invariant to test: every "
        "appointment's hospital must match its doctor's hospital.",
        "Appointment times cluster on weekday mornings. If you plot a "
        "histogram by hour you get the double-humped shape of a real clinic "
        "day, with a dip over lunch.",
    ],
)

DIAGNOSES = Entity(
    name="diagnoses",
    topic="clinical",
    grain="One row per diagnosis recorded at one completed appointment.",
    description=(
        "Conditions recorded against a patient, coded with real ICD-10 codes. "
        "Only completed appointments produce diagnoses -- a cancelled visit "
        "cannot diagnose anything, which is a rule worth testing joins "
        "against."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("patient_id", "integer", references="patients.id", example=42,
              description="The patient diagnosed. Denormalised from the "
                          "appointment so you can count diagnoses per patient "
                          "without a second join."),
        Field("appointment_id", "integer", references="appointments.id", example=88,
              description="The appointment at which this diagnosis was recorded. "
                          "Always an appointment whose status is 'completed'."),
        Field("icd10_code", "string", example="E11.9",
              description="The diagnosis code. These are genuine ICD-10 codes "
                          "from the WHO's public classification, so you can look "
                          "any of them up in an ICD browser and get the same "
                          "description that appears in the next column."),
        Field("description", "string",
              example="Type 2 diabetes mellitus without complications",
              description="The official ICD-10 description for the code. Stored "
                          "alongside rather than looked up, which is what most "
                          "real clinical systems do so that a historical record "
                          "keeps its original wording when the code set is "
                          "revised."),
        Field("severity", "enum", values=["mild", "moderate", "severe"],
              example="moderate",
              description="Clinical severity. Weighted towards mild and "
                          "moderate, as a real outpatient caseload is."),
        Field("diagnosed_at", "date", example="2024-06-14",
              description="Date of diagnosis. Always the same date as the "
                          "referenced appointment."),
        Field("is_chronic", "boolean", example=True,
              description="Whether this is an ongoing condition rather than an "
                          "acute episode. Derived from the code: diabetes and "
                          "hypertension are chronic, a fracture is not."),
    ],
)

PRESCRIPTIONS = Entity(
    name="prescriptions",
    topic="clinical",
    grain="One row per medication prescribed to one patient by one doctor.",
    description=(
        "Medicines prescribed during the period. Drug names are generic "
        "(non-brand) international nonproprietary names, which is what appears "
        "on a real prescription and carries no trademark."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("patient_id", "integer", references="patients.id", example=42,
              description="The patient the medication is for. A patient may "
                          "hold several concurrent prescriptions."),
        Field("doctor_id", "integer", references="doctors.id", example=17,
              description="The doctor who issued the prescription. Not "
                          "necessarily one the patient has an appointment with."),
        Field("medication", "string", example="Metformin",
              description="Generic drug name. Eighteen common medications, "
                          "weighted so that the drugs prescribed most often in "
                          "reality appear most often here."),
        Field("dosage", "string", example="500 mg",
              description="Strength per dose, always one that the medication is "
                          "genuinely dispensed in -- you will not find a 37 mg "
                          "Metformin tablet."),
        Field("frequency", "string", example="Twice daily with meals",
              description="Dosing instruction as it would be written on the "
                          "label, matched to the medication."),
        Field("start_date", "date", example="2024-06-14",
              description="Date the course begins. Always on or after the "
                          "patient's registration date."),
        Field("end_date", "date", nullable=True, example="2024-07-14",
              description="Date the course ends. Empty for repeat prescriptions "
                          "of chronic medication, which is about 45% of rows -- "
                          "an open-ended course is the normal case for something "
                          "like a blood pressure tablet."),
        Field("refills_allowed", "integer", example=3,
              description="How many times the prescription can be re-dispensed "
                          "without a new consultation, from 0 to 11."),
    ],
)

LAB_RESULTS = Entity(
    name="lab_results",
    topic="clinical",
    grain="One row per individual laboratory measurement.",
    description=(
        "Blood and urine test results, coded with real LOINC codes. This is "
        "the largest table in the topic and the most useful one for charting, "
        "because the values are generated from age-adjusted distributions "
        "rather than at random."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("patient_id", "integer", references="patients.id", example=42,
              description="The patient the sample was taken from. Their age "
                          "drives the value in the `value` column."),
        Field("loinc_code", "string", example="4548-4",
              description="The LOINC code identifying which test this is. LOINC "
                          "is the international standard for naming laboratory "
                          "observations, and these are genuine codes."),
        Field("test_name", "string", example="Haemoglobin A1c",
              description="Plain-language name of the assay, matching the "
                          "LOINC code in the previous column. Stored "
                          "alongside so a reader can interpret a result "
                          "without consulting a terminology server."),
        Field("value", "decimal", example=7.40,
              description="The measured result, to two decimal places. Generated "
                          "from a distribution whose mean shifts with the "
                          "patient's age, so older patients really do show "
                          "higher HbA1c and creatinine."),
        Field("unit", "string", example="%",
              description="Unit of measurement for the value. Always the unit "
                          "the LOINC code specifies -- never assume, read this "
                          "column."),
        Field("reference_low", "decimal", example=4.00,
              description="Lower bound of the normal range for this test. Below "
                          "this the result is flagged LOW."),
        Field("reference_high", "decimal", example=5.70,
              description="Upper bound of the normal range. Above this the "
                          "result is flagged HIGH."),
        Field("flag", "enum", values=["LOW", "NORMAL", "HIGH"], example="HIGH",
              description="Where the value sits relative to the reference range. "
                          "Computed from value, reference_low and "
                          "reference_high, so it is always consistent with them "
                          "-- which makes it a good column for verifying your "
                          "own derived-field logic against."),
        Field("collected_at", "datetime", example="2024-06-14T08:15:00",
              description="When the sample was taken. Phlebotomy rounds happen "
                          "early, so these cluster between 07:00 and 10:00."),
    ],
    notes=[
        "About 18% of results fall outside their reference range. That is "
        "higher than a healthy population but realistic for a hospital "
        "dataset, where people are tested because something is suspected.",
        "The `flag` column is fully derivable from `value`, `reference_low` "
        "and `reference_high`. It is stored anyway -- as real lab systems do "
        "-- which makes it a ready-made exercise: recompute it yourself and "
        "check you get the same answer for all 8,000 rows.",
    ],
)


# ===========================================================================
# PART 3 -- THE GENERATOR
# ===========================================================================
# Produces the actual rows. Each entity gets its own function and its own
# random stream, so a change to one does not shift the values of the others.
#
# Every function takes the rows it depends on as arguments -- `appointments`
# needs `patients` and `doctors` -- which is what guarantees that the foreign
# keys resolve. We are not generating an ID and hoping it exists; we are
# picking an actual row and using its actual ID.


def _strip_accents(text: str) -> str:
    """Remove Spanish diacritics: María -> Maria, Muñoz -> Munoz.

    Email addresses cannot contain accented characters in practice, so a
    Spanish name has to be transliterated before it becomes one. This is a
    real step that real systems perform, and getting it wrong produces
    addresses like "mar\u00eda.fern\u00e1ndez@..." that silently bounce.

    NFKD decomposition splits "í" into "i" plus a combining accent mark; the
    ASCII encode then drops the mark and keeps the letter. "ñ" is handled
    separately because it is a letter in its own right in Spanish, not an
    accented "n" -- but an email address still has to spell it "n".
    """
    text = text.replace("ñ", "n").replace("Ñ", "N")
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def _email_from_name(full_name: str, domain: str, rng: Rng) -> str:
    """Build an email address from a person's name.

    Real corporate addresses follow a pattern (first.surname@), so deriving
    the address from the name rather than generating it independently is
    what makes the two columns look like they belong to the same person.

    Spanish people carry two surnames -- "María Fernández Ruiz" -- and the
    usual convention is to use the first of them, giving
    "maria.fernandez@...". Taking the last word instead would produce
    "maria.ruiz@", which is the mother's surname and not what anybody uses.
    """
    cleaned = _strip_accents(full_name)
    for title in ("Dr. ", "Dra. ", "D. ", "Dña. "):
        cleaned = cleaned.replace(title, "")
    cleaned = cleaned.replace("'", "").replace(".", "")
    parts = [part.lower() for part in cleaned.split() if part]
    stem = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
    # A few people collide; a numeric suffix is what a real IT department does.
    suffix = "" if rng.python.random() > 0.08 else str(rng.python.randint(2, 9))
    return f"{stem}{suffix}@{domain}"


def _generate_hospitals(count: int) -> list[dict[str, Any]]:
    rng = Rng("clinical", "hospitals")

    # Spanish hospitals are named in a handful of recognisable patterns: a
    # religious dedication ("Hospital Virgen del Espino"), the city they
    # serve ("Hospital General de Sevilla"), or a role descriptor
    # ("Hospital Universitario", "Hospital Comarcal").
    #
    # The dedications below are INVENTED. They use the same saints-and-
    # virgins naming convention as real Spanish hospitals, but the specific
    # combinations do not name an existing institution.
    dedications = [
        "San Anselmo", "Santa Engracia", "Virgen de los Álamos",
        "San Teodoro", "Nuestra Señora del Alba", "San Fulgencio",
        "Santa Perpetua", "San Adriano", "Virgen del Espino", "Santa Inés",
        "San Baudilio", "Nuestra Señora del Robledo", "San Hilario",
        "Santa Genoveva", "San Cosme", "Virgen de la Alameda",
        "San Emeterio", "Santa Rosalía", "San Quirico", "Virgen del Mirador",
        "San Ildefonso", "Santa Eulalia", "San Bruno", "Virgen de la Peña",
        "Santa Columba",
    ]

    # Which naming pattern suits which kind of hospital. A teaching hospital
    # in Spain is almost always "Universitario" or "Clínico"; a small local
    # one is "Comarcal" or a "Centro de Salud".
    patterns_by_type = {
        "Teaching": ["Hospital Universitario {dedication}",
                     "Hospital Clínico {dedication}"],
        "General": ["Hospital General de {city}", "Hospital {dedication}"],
        # "Comarcal" describes a hospital serving a rural comarca, so it is
        # reserved for the smaller cities below -- "Hospital Comarcal de
        # Madrid" is a contradiction in terms.
        "Community": ["Centro de Salud {dedication}",
                      "Hospital Comarcal de {city}"],
        "Specialist": ["Instituto {dedication}", "Clínica {dedication}"],
        "Children's": ["Hospital Infantil {dedication}",
                       "Hospital Materno-Infantil {dedication}"],
    }

    # Bed capacity by hospital type -- (mean, standard deviation). Teaching
    # hospitals are large, community hospitals small. This is what makes a
    # "average beds by type" chart look sensible.
    beds_by_type = {
        "Teaching": (700, 140),
        "General": (400, 110),
        "Specialist": (220, 70),
        "Community": (120, 45),
        "Children's": (180, 50),
    }

    rows = []
    used_names: set[str] = set()
    for index in range(1, count + 1):
        hospital_type = rng.weighted_choice(HOSPITAL_TYPES)
        mean, sd = beds_by_type[hospital_type]
        beds = int(max(40, min(900, rng.numpy.normal(mean, sd))))

        location = generate_address(rng, with_phone=True)

        # Names must be unique, so take each dedication once and fall back to
        # the city pattern if a collision would occur.
        dedication = dedications[(index - 1) % len(dedications)]
        patterns = [
            pattern for pattern in patterns_by_type[hospital_type]
            if not ("Comarcal" in pattern and location["city"] in MAJOR_CITIES)
        ]
        pattern = rng.python.choice(patterns)
        name = pattern.format(dedication=dedication, city=location["city"])
        while name in used_names:
            dedication = rng.python.choice(dedications)
            pattern = rng.python.choice(patterns)
            name = pattern.format(dedication=dedication, city=location["city"])
        used_names.add(name)

        rows.append({
            "id": index,
            "name": name,
            "type": hospital_type,
            "city": location["city"],
            "province": location["province"],
            "address": location["address"],
            "postal_code": location["postal_code"],
            "phone": location["phone"],
            "beds": beds,
            "founded": rng.python.randint(1890, 2015),
        })
    return rows


def _generate_departments(hospitals: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("clinical", "departments")

    # How many departments a hospital has, by type. A community hospital
    # does not run a neurosurgery unit; a teaching hospital runs nearly
    # everything. Generating this properly is why `departments` is not simply
    # every hospital crossed with every department name.
    departments_by_type = {
        "Teaching": (9, 12),
        "General": (6, 9),
        "Specialist": (2, 4),
        "Community": (3, 5),
        "Children's": (3, 5),
    }

    all_names = sorted(DEPARTMENTS)
    rows: list[dict[str, Any]] = []
    next_id = 1

    for hospital in hospitals:
        low, high = departments_by_type[hospital["type"]]
        how_many = rng.python.randint(low, min(high, len(all_names)))
        chosen = rng.python.sample(all_names, how_many)

        for name in sorted(chosen):
            rows.append({
                "id": next_id,
                "hospital_id": hospital["id"],
                "name": name,
                "floor": rng.python.randint(0, 8),
                "phone_extension": f"{rng.python.randint(1000, 9999)}",
            })
            next_id += 1

            if len(rows) >= count:
                return rows

    return rows


def _generate_doctors(
    hospitals: list[dict], departments: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("clinical", "doctors")

    hospitals_by_id = {hospital["id"]: hospital for hospital in hospitals}
    rows = []

    for index in range(1, count + 1):
        # Pick a real department row, then take its hospital from that row.
        # This is the pattern that makes foreign keys resolve: never invent an
        # ID, always take one from a row that exists.
        department = rng.python.choice(departments)
        hospital = hospitals_by_id[department["hospital_id"]]

        # Spanish titles are gendered, so the name and the title have to be
        # chosen together: "Dra. Lucía Fernández" but "Dr. Javier Fernández".
        is_female = rng.python.random() < 0.52
        person = rng.faker.name_female() if is_female else rng.faker.name_male()
        full_name = f"{'Dra.' if is_female else 'Dr.'} {person}"

        # Doctors are between 28 and 70. Hire date has to be old enough that
        # they had qualified -- no 19-year-old consultants.
        age = rng.python.randint(28, 70)
        earliest_hire = add_years(AS_OF, -(age - 26))
        hired_at = rng.date_between(max(earliest_hire, date(1985, 1, 1)), AS_OF)

        # The qualification has to be one that existed when this doctor
        # qualified -- see BOLOGNA_FIRST_GRADUATES above.
        qualification = rng.python.choice(
            POST_BOLOGNA_QUALIFICATIONS
            if hired_at.year >= BOLOGNA_FIRST_GRADUATES
            else PRE_BOLOGNA_QUALIFICATIONS
        )

        rows.append({
            "id": index,
            "hospital_id": hospital["id"],
            "department_id": department["id"],
            "full_name": full_name,
            "specialty": rng.python.choice(DEPARTMENTS[department["name"]]),
            "license_number": business_key("LIC", index),
            "email": _email_from_name(full_name, "example.org", rng),
            "hired_at": hired_at,
            "qualification": qualification,
        })
    return rows


def _generate_patients(count: int) -> list[dict[str, Any]]:
    rng = Rng("clinical", "patients")

    # A population pyramid, as (age_band, relative_weight). Roughly matches a
    # developed-country age structure. Sampling from this instead of
    # uniform(0, 98) is what makes every downstream age-dependent value --
    # every lab result -- look clinically plausible.
    age_bands = [
        ((0, 9),   105), ((10, 19), 110), ((20, 29), 125), ((30, 39), 135),
        ((40, 49), 130), ((50, 59), 132), ((60, 69), 115), ((70, 79), 85),
        ((80, 89), 45),  ((90, 98), 12),
    ]
    bands = [band for band, _ in age_bands]
    weights = [weight for _, weight in age_bands]

    rows = []
    for index in range(1, count + 1):
        low, high = rng.python.choices(bands, weights=weights, k=1)[0]
        age = rng.python.randint(low, high)

        # Convert the age into a date of birth somewhere inside that year.
        birth_year = AS_OF.year - age
        date_of_birth = date(birth_year, 1, 1) + timedelta(
            days=rng.python.randint(0, 364)
        )
        if date_of_birth > AS_OF:
            date_of_birth = add_years(date_of_birth, -1)

        sex = rng.python.choice(["F", "M"])
        full_name = rng.faker.name_female() if sex == "F" else rng.faker.name_male()

        # Older patients are markedly less likely to have an email address on
        # file. Small touch, but it is the kind of correlation that makes a
        # dataset feel observed rather than manufactured.
        email_missing_probability = 0.05 + min(0.45, max(0.0, (age - 45) * 0.012))

        # Three quarters of Spanish contact numbers on file are mobiles.
        location = generate_address(
            rng, with_phone=True, mobile=rng.python.random() < 0.75
        )
        rows.append({
            "id": index,
            "mrn": business_key("MRN", index),
            "full_name": full_name,
            "date_of_birth": date_of_birth,
            "sex": sex,
            "blood_type": rng.weighted_choice(BLOOD_TYPES),
            "phone": rng.maybe_null(location["phone"], 0.05),
            "email": rng.maybe_null(
                _email_from_name(full_name, "example.com", rng),
                email_missing_probability,
            ),
            "address": location["address"],
            "city": location["city"],
            "province": location["province"],
            "postal_code": location["postal_code"],
            "registered_at": rng.date_between(PERIOD_START, date(2025, 3, 31)),
        })
    return rows


def _generate_insurance_policies(patients: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("clinical", "insurance_policies")

    # Take a sample of patients -- the rest are uninsured, on purpose, so
    # there is something for a LEFT JOIN to miss.
    insured = rng.python.sample(patients, min(count, len(patients)))
    insured.sort(key=lambda patient: patient["id"])

    premium_by_level = {
        "Basic": 1100, "Standard": 2200, "Premium": 3600, "Comprehensive": 5400,
    }

    rows = []
    for index, patient in enumerate(insured, start=1):
        level = rng.weighted_choice(COVERAGE_LEVELS)
        age = age_on(patient["date_of_birth"], AS_OF)

        # Premium rises with age and with the tier, plus a little noise.
        base = premium_by_level[level]
        age_loading = 1.0 + max(0.0, (age - 30)) * 0.011
        premium = round(base * age_loading * rng.numpy.normal(1.0, 0.07), 2)

        valid_from = rng.date_between(PERIOD_START, date(2025, 1, 1))
        rows.append({
            "id": index,
            "patient_id": patient["id"],
            "provider": rng.python.choice(sorted(INSURANCE_PROVIDERS)),
            "policy_number": business_key("POL", index, width=8),
            "coverage_level": level,
            "annual_premium": max(400.0, round(float(premium), 2)),
            "valid_from": valid_from,
            "valid_until": add_years(valid_from, rng.python.randint(1, 3)),
        })
    return rows


def _generate_appointments(
    patients: list[dict], doctors: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("clinical", "appointments")

    # Clinic slot times: 08:00 to 17:30 on 15-minute boundaries, weighted so
    # mornings are busier and the lunch hour dips. Plotting appointments by
    # hour then gives the familiar double hump of a real clinic day.
    slot_weights: dict[time, int] = {}
    for hour in range(8, 18):
        if hour in (12, 13):
            weight = 4          # lunch dip
        elif hour < 12:
            weight = 12         # busy morning
        else:
            weight = 9          # steadier afternoon
        for minute in (0, 15, 30, 45):
            if hour == 17 and minute > 30:
                continue
            slot_weights[time(hour, minute)] = weight

    duration_weights = {15: 30, 20: 20, 30: 32, 45: 12, 60: 6}
    past_status_weights = {"completed": 78, "cancelled": 10, "no_show": 7, "scheduled": 5}

    rows = []
    for index in range(1, count + 1):
        patient = rng.python.choice(patients)
        doctor = rng.python.choice(doctors)

        # The appointment cannot happen before the patient registered.
        earliest = max(PERIOD_START, patient["registered_at"])
        latest = min(PERIOD_END, AS_OF + timedelta(days=BOOKING_HORIZON_DAYS))
        appointment_date = rng.date_between(earliest, max(earliest, latest))

        # Clinics do not run at weekends in this dataset. Nudge Saturday and
        # Sunday forward to the following Monday.
        appointment_date = next_weekday(appointment_date)

        slot = rng.weighted_choice(slot_weights)
        scheduled_at = datetime.combine(appointment_date, slot)

        if appointment_date > AS_OF:
            status = "scheduled"
        else:
            status = rng.weighted_choice(past_status_weights)

        reason = rng.python.choice(sorted(APPOINTMENT_REASONS))
        # New referrals and pre-operative assessments genuinely take longer.
        if reason in ("New referral", "Pre-operative assessment", "Second opinion"):
            duration = rng.python.choice([30, 45, 60])
        else:
            duration = rng.weighted_choice(duration_weights)

        # A note is written up only when the patient actually attended.
        if status == "completed" and rng.python.random() < 0.60:
            notes = rng.python.choice([
                "Patient reports improvement since last review.",
                "Symptoms stable. Continue current management.",
                "Discussed medication adherence; no changes made.",
                "Requested repeat bloods before next appointment.",
                "Referred onward for further imaging.",
                "Reviewed test results with patient; reassurance given.",
                "Advised lifestyle modification and follow-up in three months.",
                "No new concerns raised. Routine review scheduled.",
            ])
        else:
            notes = None

        rows.append({
            "id": index,
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            # Taken from the doctor's row, never invented -- this is what
            # keeps the "appointment hospital == doctor hospital" invariant
            # true by construction rather than by luck.
            "hospital_id": doctor["hospital_id"],
            "scheduled_at": scheduled_at,
            "duration_minutes": duration,
            "status": status,
            "reason": reason,
            "notes": notes,
        })

    rows.sort(key=lambda row: row["scheduled_at"])
    for new_id, row in enumerate(rows, start=1):
        row["id"] = new_id
    return rows


def _generate_diagnoses(appointments: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("clinical", "diagnoses")

    # Only completed appointments can produce a diagnosis. A cancelled visit
    # diagnosing something would be a data-quality bug in a real system.
    completed = [row for row in appointments if row["status"] == "completed"]
    if not completed:
        return []

    codes = [entry[0] for entry in ICD10_CODES]
    descriptions = {entry[0]: entry[1] for entry in ICD10_CODES}
    weights = [entry[3] for entry in ICD10_CODES]

    # Conditions that are ongoing rather than one-off episodes.
    chronic_codes = {
        "I10", "E11.9", "E78.5", "J45.909", "M17.9", "E03.9", "I48.91",
        "J44.9", "L20.9", "G47.33", "N18.3", "I25.10", "F32.9", "F41.1",
        "K21.9", "C50.911",
    }

    severity_weights = {"mild": 45, "moderate": 40, "severe": 15}

    rows = []
    for index in range(1, count + 1):
        appointment = rng.python.choice(completed)
        code = rng.python.choices(codes, weights=weights, k=1)[0]

        rows.append({
            "id": index,
            "patient_id": appointment["patient_id"],
            "appointment_id": appointment["id"],
            "icd10_code": code,
            "description": descriptions[code],
            "severity": rng.weighted_choice(severity_weights),
            "diagnosed_at": appointment["scheduled_at"].date(),
            "is_chronic": code in chronic_codes,
        })
    return rows


def _generate_prescriptions(
    patients: list[dict], doctors: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("clinical", "prescriptions")

    # Weighted so the medications prescribed most often in reality -- statins,
    # blood pressure tablets, metformin -- dominate the table.
    medication_weights = [
        60, 55, 58, 50, 48, 42, 38, 36, 34, 45,
        50, 30, 32, 26, 20, 18, 16, 28,
    ]

    rows = []
    for index in range(1, count + 1):
        patient = rng.python.choice(patients)
        doctor = rng.python.choice(doctors)
        name, dosages, frequency = rng.python.choices(
            MEDICATIONS, weights=medication_weights, k=1
        )[0]

        start_date = rng.date_between(max(PERIOD_START, patient["registered_at"]), AS_OF)

        # Repeat prescriptions for chronic medication have no end date. That
        # is the normal case for something like a blood-pressure tablet, and
        # it is why `end_date` is nullable.
        if rng.python.random() < 0.45:
            end_date = None
            refills = rng.python.randint(5, 11)
        else:
            end_date = start_date + timedelta(days=rng.python.choice([7, 14, 28, 56, 90]))
            refills = rng.python.randint(0, 3)

        rows.append({
            "id": index,
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "medication": name,
            "dosage": rng.python.choice(dosages),
            "frequency": frequency,
            "start_date": start_date,
            "end_date": end_date,
            "refills_allowed": refills,
        })
    return rows


def _generate_lab_results(patients: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("clinical", "lab_results")

    rows = []
    for index in range(1, count + 1):
        patient = rng.python.choice(patients)
        age = age_on(patient["date_of_birth"], AS_OF)

        code, name, unit, ref_low, ref_high, mean, sd, age_slope = rng.python.choice(LAB_TESTS)

        # THIS is the line that makes the lab data worth having.
        #
        # The mean of the distribution shifts with the patient's age, so a
        # 78-year-old's HbA1c really is higher than a 24-year-old's. Generate
        # the value independently of age and you get numbers that parse fine
        # but fall apart the moment anyone plots them against anything.
        age_adjusted_mean = mean + age_slope * (age - 40)
        value = float(rng.numpy.normal(age_adjusted_mean, sd))
        value = max(0.01, round(value, 2))

        if value < ref_low:
            flag = "LOW"
        elif value > ref_high:
            flag = "HIGH"
        else:
            flag = "NORMAL"

        # Phlebotomy rounds run early -- most samples are taken before 10am.
        collected_date = rng.date_between(
            max(PERIOD_START, patient["registered_at"]), AS_OF
        )
        collected_date = next_weekday(collected_date)
        collected_at = datetime.combine(
            collected_date,
            time(rng.python.choices([7, 8, 9, 10, 11, 14, 15],
                                    weights=[18, 26, 22, 12, 8, 8, 6], k=1)[0],
                 rng.python.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])),
        )

        rows.append({
            "id": index,
            "patient_id": patient["id"],
            "loinc_code": code,
            "test_name": name,
            "value": value,
            "unit": unit,
            "reference_low": ref_low,
            "reference_high": ref_high,
            "flag": flag,
            "collected_at": collected_at,
        })

    rows.sort(key=lambda row: row["collected_at"])
    for new_id, row in enumerate(rows, start=1):
        row["id"] = new_id
    return rows


def generate(scale: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    """Produce every table in the clinical topic.

    Parameters
    ----------
    scale
        Multiplier on DEFAULT_COUNTS. ``scale=10`` gives ten times as many
        rows, for load testing. The relationships hold at any scale.

    Returns
    -------
    A dict of ``{entity_name: list_of_row_dicts}``, in dependency order --
    parents before children, so it can be inserted into SQLite as-is.
    """
    counts = {name: max(1, int(number * scale)) for name, number in DEFAULT_COUNTS.items()}

    hospitals = _generate_hospitals(counts["hospitals"])
    departments = _generate_departments(hospitals, counts["departments"])
    doctors = _generate_doctors(hospitals, departments, counts["doctors"])
    patients = _generate_patients(counts["patients"])
    insurance_policies = _generate_insurance_policies(patients, counts["insurance_policies"])
    appointments = _generate_appointments(patients, doctors, counts["appointments"])
    diagnoses = _generate_diagnoses(appointments, counts["diagnoses"])
    prescriptions = _generate_prescriptions(patients, doctors, counts["prescriptions"])
    lab_results = _generate_lab_results(patients, counts["lab_results"])

    return {
        "hospitals": hospitals,
        "departments": departments,
        "doctors": doctors,
        "patients": patients,
        "insurance_policies": insurance_policies,
        "appointments": appointments,
        "diagnoses": diagnoses,
        "prescriptions": prescriptions,
        "lab_results": lab_results,
    }


# ===========================================================================
# The topic object -- what build.py imports.
# ===========================================================================

TOPIC = Topic(
    name="clinical",
    title="Clinical / Healthcare",
    summary=(
        "Hospitals, doctors, patients, appointments, diagnoses, prescriptions "
        "and laboratory results, coded with real ICD-10 and LOINC standards."
    ),
    description=(
        "A synthetic hospital network spanning twenty-five sites across "
        "Spain, with three years of appointments, diagnoses, prescriptions "
        "and blood test results. Exact row counts are in the table below, "
        "which is generated from the data itself and therefore always "
        "current.\n\n"
        "The diagnosis codes are genuine ICD-10 codes and the laboratory "
        "codes are genuine LOINC codes -- both are public international "
        "standards rather than patient data, which means you can test a real "
        "terminology lookup against them. Everything else, every person and "
        "every hospital, is invented.\n\n"
        "Laboratory values are generated from age-adjusted distributions, so "
        "the data is genuinely usable for demonstrating analysis rather than "
        "only for testing that your CSV parser works."
    ),
    entities=[
        HOSPITALS,
        DEPARTMENTS_ENTITY,
        DOCTORS,
        PATIENTS,
        INSURANCE_POLICIES,
        APPOINTMENTS,
        DIAGNOSES,
        PRESCRIPTIONS,
        LAB_RESULTS,
    ],
)
