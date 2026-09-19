"""
Topic: education -- schools, students, courses, grades and attendance.
===============================================================================

WHAT IS THIS TOPIC FOR?
-----------------------
A student information system, a gradebook, a timetabling tool, an attendance
tracker, or a parent portal. It is also the best topic in this repository
for demonstrating ANALYSIS rather than parsing, because it is the only one
with a deliberate signal buried in it (see below).

WHAT MAKES IT REALISTIC
-----------------------
1. **There is a real correlation to find.** Every student carries a hidden
   diligence factor that drives BOTH how often they turn up and how well
   they score. Neither is stored -- only the attendance records and the
   grades are -- so the relationship between attendance and achievement is
   genuinely emergent. Plot mean grade against attendance rate and you get a
   real upward slope with realistic scatter.

   That makes this topic useful for teaching data analysis, demonstrating a
   dashboard, or testing a correlation feature. Random data has nothing to
   find and every chart drawn on it looks like static.

2. **Grades use the Spanish 0-10 scale.** Not A-F. Five is a pass, and the
   named bands (suspenso, aprobado, bien, notable, sobresaliente) are the
   ones a Spanish report card actually prints.

3. **Weighted components add up.** Each enrolment's assessments carry
   weights summing to exactly 1.00, and the enrolment's final grade is
   exactly that weighted sum. Verified in CI.

4. **The school system is Spanish.** Primaria, ESO, Bachillerato and FP,
   with age ranges and subject lists that match the real curriculum.

READ clinical.py FIRST -- it is the fully commented reference
implementation, and this file follows the same three-part shape.
"""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from ..common.dates import next_weekday
from ..common.geography import PROVINCES, generate_address
from ..common.identifiers import dni
from ..common.schema import Entity, Field, Topic
from ..common.seeds import Rng

# ===========================================================================
# PART 1 -- REFERENCE DATA
# ===========================================================================

DEFAULT_COUNTS = {
    "schools": 10,
    "classrooms": 120,
    "teachers": 200,
    "courses": 300,
    "students": 900,
    "exams": 300,
    "enrollments": 1_800,
    "attendance": 18_000,
    "grades": 5_400,
}

#: Recorded teaching sessions per enrolment.
#:
#: This is a fixed number rather than a share of the attendance budget, and
#: it matters more than it looks. `attendance_rate` is computed by counting
#: attended sessions against total sessions, so with one session per
#: enrolment the rate could only ever be 0.0 or 1.0 -- which would destroy
#: the correlation with achievement that this topic exists to demonstrate.
#: Ten gives a rate in steps of 0.1, enough for a scatter plot to show a
#: real slope.
SESSIONS_PER_ENROLLMENT = 10

#: The academic years covered. Spanish school years run September to June
#: and are written "2023/2024".
ACADEMIC_YEARS = ["2022/2023", "2023/2024", "2024/2025"]

PERIOD_START = date(2022, 9, 12)
PERIOD_END = date(2025, 6, 20)

#: Spanish school types.
#:
#: CEIP is a state infant-and-primary school, IES a state secondary school.
#: "Concertado" is the Spanish middle category: privately run but
#: state-funded, which has no direct equivalent in most countries and is
#: worth having in the data precisely because of that.
SCHOOL_TYPES = {
    "CEIP": 30,          # state primary
    "IES": 34,           # state secondary
    "Concertado": 24,    # state-funded private
    "Privado": 12,       # fully private
}

#: Educational stages in the Spanish system, with the ages they cover.
#:
#: Primaria    6-12   six years, called 1º to 6º de Primaria
#: ESO         12-16  compulsory secondary, 1º to 4º de ESO
#: Bachillerato 16-18 pre-university, 1º and 2º
#: FP          16+    vocational training
STAGES = {
    "Primaria": (6, 12, 6),
    "ESO": (12, 16, 4),
    "Bachillerato": (16, 18, 2),
    "FP": (16, 20, 2),
}

#: Which stages each school type teaches. A CEIP does not run Bachillerato.
STAGES_BY_SCHOOL_TYPE = {
    "CEIP": ["Primaria"],
    "IES": ["ESO", "Bachillerato", "FP"],
    "Concertado": ["Primaria", "ESO", "Bachillerato"],
    "Privado": ["Primaria", "ESO", "Bachillerato"],
}

#: Subjects per stage, in Spanish, as they appear on a Spanish timetable.
SUBJECTS = {
    "Primaria": [
        "Matemáticas", "Lengua Castellana", "Ciencias Naturales",
        "Ciencias Sociales", "Inglés", "Educación Física",
        "Educación Artística", "Música", "Religión / Valores",
    ],
    "ESO": [
        "Matemáticas", "Lengua Castellana y Literatura", "Inglés",
        "Geografía e Historia", "Biología y Geología", "Física y Química",
        "Educación Física", "Tecnología", "Música", "Educación Plástica",
        "Francés", "Valores Éticos",
    ],
    "Bachillerato": [
        "Matemáticas I", "Matemáticas II", "Lengua Castellana y Literatura",
        "Inglés", "Historia de España", "Historia de la Filosofía",
        "Física", "Química", "Biología", "Geología",
        "Dibujo Técnico", "Economía", "Latín", "Griego", "Literatura Universal",
    ],
    "FP": [
        "Sistemas Informáticos", "Bases de Datos", "Programación",
        "Formación y Orientación Laboral", "Empresa e Iniciativa Emprendedora",
        "Gestión Administrativa", "Contabilidad", "Inglés Técnico",
    ],
}

#: Teacher specialities map onto the subject groupings a Spanish school uses
#: for its departments.
DEPARTMENTS = [
    "Matemáticas", "Lengua y Literatura", "Idiomas", "Ciencias",
    "Ciencias Sociales", "Tecnología", "Educación Física",
    "Artes", "Orientación", "Formación Profesional",
]

QUALIFICATIONS = {
    "Grado en Educación Primaria": 22,
    "Grado + Máster en Formación del Profesorado": 34,
    "Licenciatura + CAP": 26,
    "Doctorado": 8,
    "Técnico Superior FP": 10,
}

CONTRACT_TYPES = {"permanent": 54, "interim": 32, "temporary": 14}

ENROLLMENT_STATUSES = {"completed": 82, "in_progress": 12,
                       "withdrawn": 4, "repeated": 2}

#: Assessment components and the weights they typically carry. The weights
#: for one enrolment always sum to exactly 1.00.
ASSESSMENT_TYPES = ["exam", "coursework", "practical", "participation"]

ATTENDANCE_STATUSES = {"present": 88, "absent": 6, "late": 4, "excused": 2}

EXAM_TYPES = {"midterm": 38, "final": 34, "resit": 12, "mock": 16}

#: The Spanish 0-10 grading scale and its named bands, exactly as they are
#: printed on a report card. Anything below 5 is a fail.
GRADE_BANDS = [
    (0.0, 4.99, "Suspenso"),
    (5.0, 5.99, "Aprobado"),
    (6.0, 6.99, "Bien"),
    (7.0, 8.99, "Notable"),
    (9.0, 10.0, "Sobresaliente"),
]


def grade_band(score: float) -> str:
    """Return the Spanish name for a 0-10 score.

    >>> grade_band(4.2), grade_band(5.5), grade_band(7.0), grade_band(9.5)
    ('Suspenso', 'Aprobado', 'Notable', 'Sobresaliente')
    """
    for low, high, name in GRADE_BANDS:
        if low <= score <= high:
            return name
    return "Sobresaliente"


# ===========================================================================
# PART 2 -- THE SCHEMA
# ===========================================================================

SCHOOLS = Entity(
    name="schools",
    topic="education",
    grain="One row per school centre in the network.",
    description=(
        "The institutions themselves. Teachers, classrooms, courses and "
        "students all belong to exactly one school, so this is the root of "
        "the whole topic."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Every "
                          "other table in this topic joins against it."),
        Field("code", "string", unique=True, pattern=r"^\d{8}$", example="41000123",
              description="Centre code in the format Spanish education "
                          "authorities use: two digits for the province, then "
                          "six identifying the centre. Invented, but "
                          "structurally correct."),
        Field("name", "string", unique=True, example="IES Miguel de Unamuno",
              description="School name, following real Spanish conventions -- "
                          "the centre type followed by a person or place name. "
                          "All invented."),
        Field("type", "enum", values=sorted(SCHOOL_TYPES), example="IES",
              description="Centre type. CEIP is state primary, IES state "
                          "secondary, Concertado privately run but state "
                          "funded, and Privado fully independent. The type "
                          "determines which stages the school teaches."),
        Field("city", "string", example="Sevilla",
              description="Spanish city the school is in, drawn from real "
                          "municipalities weighted by population."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province the school sits in, always consistent "
                          "with the first two digits of its postal code."),
        Field("address", "string", example="Calle de la Constitución, 24",
              description="Street address in Spanish format, with the number "
                          "after the street name. Invented."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41004",
              description="Spanish postal code whose leading pair encodes the "
                          "province, so the two columns always agree."),
        Field("phone", "string", example="+34 954 22 41 08",
              description="School office number, carrying the dialling prefix "
                          "of the province it is in."),
        Field("student_capacity", "integer", unit="students", example=850,
              description="How many pupils the site can hold, correlated with "
                          "centre type -- a CEIP is far smaller than an IES."),
        Field("founded", "integer", unit="year", example=1974,
              description="Calendar year the centre first admitted pupils, "
                          "spread between 1900 and 2018. No teacher in this "
                          "dataset was hired before their own school "
                          "existed."),
    ],
)

TEACHERS = Entity(
    name="teachers",
    topic="education",
    grain="One row per member of teaching staff.",
    description=(
        "Teachers, each attached to one school and one department. A teacher "
        "leads several courses, which is how this table connects to the rest "
        "of the topic."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("school_id", "integer", references="schools.id", example=1,
              description="Which school employs this teacher. Everybody is "
                          "attached to exactly one centre in this dataset."),
        Field("teacher_code", "string", unique=True, pattern=r"^PRF-\d{5}$",
              example="PRF-00042",
              description="Staff reference used on timetables and internal "
                          "systems, quoted instead of the numeric id."),
        Field("full_name", "string", example="Ana Belén Ortega Ruiz",
              description="Spanish name with two surnames, the father's then "
                          "the mother's. A useful stress test for any code "
                          "that assumes one surname."),
        Field("national_id", "string", unique=True, pattern=r"^\d{8}[A-Z]$",
              example="12345678Z",
              description="Spanish DNI, eight digits and a check letter "
                          "derived modulo 23, so it passes a real validator "
                          "while belonging to nobody."),
        Field("department", "enum", values=sorted(DEPARTMENTS), example="Matemáticas",
              description="Departmental grouping the teacher belongs to. "
                          "Courses they lead are always in a subject that "
                          "department covers."),
        Field("email", "string", example="ana.ortega@example.org",
              description="Work address on the reserved example.org domain, "
                          "built from the name with accents transliterated "
                          "away."),
        Field("qualification", "enum", values=sorted(QUALIFICATIONS),
              example="Grado + Máster en Formación del Profesorado",
              description="Teaching credential. Spain requires a subject "
                          "degree plus the Máster en Formación del Profesorado "
                          "to teach secondary; primary teachers hold a "
                          "dedicated Grado en Educación Primaria."),
        Field("contract_type", "enum", values=sorted(CONTRACT_TYPES), example="permanent",
              description="Employment status. 'interim' covers the "
                          "substantial share of Spanish teachers on "
                          "year-to-year interim appointments rather than "
                          "tenured posts."),
        Field("hired_at", "date", example="2015-09-01",
              description="Start date, always the first of September because "
                          "Spanish teaching contracts begin with the academic "
                          "year, and never before the school was founded."),
    ],
)

CLASSROOMS = Entity(
    name="classrooms",
    topic="education",
    grain="One row per teaching room in one school.",
    description=(
        "Physical rooms. Exams are scheduled into a classroom, which is what "
        "makes this table useful for testing timetabling and room-clash "
        "detection."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("school_id", "integer", references="schools.id", example=1,
              description="Which school the room is in. Rooms are never shared "
                          "between centres."),
        Field("room_code", "string", example="A-204",
              description="Room reference as it appears on a timetable: a "
                          "building letter, then the floor and room number."),
        Field("building", "string", example="Edificio A",
              description="Which building on the site, in Spanish. Larger "
                          "schools have several; small ones have only one."),
        Field("floor", "integer", example=2,
              description="Which floor the room is on, from 0 for the ground "
                          "floor up to 3."),
        Field("capacity", "integer", unit="seats", example=30,
              description="How many students the room seats, typically between "
                          "15 for a specialist lab and 40 for a lecture room."),
        Field("room_type", "enum",
              values=["standard", "laboratory", "computer_lab", "workshop", "gym", "music"],
              example="standard",
              description="What the room is equipped for. Standard classrooms "
                          "dominate; labs and workshops are attached to the "
                          "subjects that need them."),
    ],
)

COURSES = Entity(
    name="courses",
    topic="education",
    grain="One row per course taught in one academic year.",
    description=(
        "A subject taught at a particular year-group level by a particular "
        "teacher in a particular academic year. The same subject at the same "
        "level in two different years is two rows, because the enrolments and "
        "grades differ."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("school_id", "integer", references="schools.id", example=1,
              description="Which school runs the course. Always the same "
                          "school as the teacher who leads it."),
        Field("teacher_id", "integer", references="teachers.id", example=7,
              description="Who teaches it. Always someone whose department "
                          "covers this subject and who works at this school."),
        Field("code", "string", unique=True, pattern=r"^[A-Z]{3}-\d{5}$",
              example="MAT-00142",
              description="Course code, three letters from the subject plus a "
                          "sequence -- the format that appears on a "
                          "timetable and a report card."),
        Field("title", "string", example="Matemáticas II",
              description="Subject name in Spanish, drawn from the real "
                          "curriculum for the stage the course belongs to."),
        Field("stage", "enum", values=sorted(STAGES), example="Bachillerato",
              description="Educational stage: Primaria for ages 6-12, ESO for "
                          "compulsory secondary, Bachillerato for "
                          "pre-university, FP for vocational training."),
        Field("year_level", "integer", example=2,
              description="Which year within the stage, numbered from 1. "
                          "Primaria runs 1 to 6, ESO 1 to 4, Bachillerato and "
                          "FP 1 to 2, exactly as the Spanish system does."),
        Field("academic_year", "enum", values=ACADEMIC_YEARS, example="2024/2025",
              description="The school year the course ran in, written the "
                          "Spanish way as a span from September to June."),
        Field("hours_per_week", "integer", unit="hours", example=4,
              description="Timetabled contact hours per week, from 1 for a "
                          "minor subject to 5 for a core one like Matemáticas "
                          "or Lengua."),
    ],
)

STUDENTS = Entity(
    name="students",
    topic="education",
    grain="One row per enrolled pupil.",
    description=(
        "The pupils. Enrolments, grades and attendance all point back here, "
        "and the guardian contact details are what a parent portal would "
        "use."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Use this "
                          "for joins rather than the student code."),
        Field("school_id", "integer", references="schools.id", example=1,
              description="Which school the pupil attends. Always a school "
                          "that teaches a stage appropriate to their age."),
        Field("student_code", "string", unique=True, pattern=r"^ALU-\d{6}$",
              example="ALU-000042",
              description="The pupil's reference at the centre, printed on a "
                          "student card and used on every internal list."),
        Field("full_name", "string", example="Lucía Serrano Gil",
              description="Spanish name with both surnames, as it appears on "
                          "the school register."),
        Field("birth_date", "date", example="2010-04-22",
              description="Date of birth. Always consistent with the stage the "
                          "pupil is enrolled in -- a Bachillerato student is "
                          "16 to 18, a Primaria pupil 6 to 12."),
        Field("sex", "enum", values=["F", "M"], example="F",
              description="Recorded sex, split close to evenly. Present "
                          "because official Spanish education statistics are "
                          "reported broken down by it."),
        Field("stage", "enum", values=sorted(STAGES), example="ESO",
              description="Which educational stage the pupil is currently in, "
                          "derived from their age and consistent with the "
                          "courses they are enrolled in."),
        Field("year_level", "integer", example=3,
              description="Year within the stage, numbered from 1 and matching "
                          "the pupil's age within that stage."),
        Field("guardian_name", "string", example="Manuel Serrano Ortiz",
              description="Parent or guardian, usually sharing one of the "
                          "pupil's surnames -- which is exactly what Spanish "
                          "naming produces and what a family-matching feature "
                          "should be tested against."),
        Field("guardian_phone", "string", example="+34 612 34 56 78",
              description="Guardian's mobile number in Spanish format. Never "
                          "empty, because a school cannot enrol a minor "
                          "without a contact number."),
        Field("guardian_email", "string", nullable=True,
              example="manuel.serrano@example.com",
              description="Guardian's email on the reserved example.com "
                          "domain. Empty for about 14% of families, which is "
                          "the gap any parent-portal rollout runs into."),
        Field("enrolled_on", "date", example="2022-09-12",
              description="Date the pupil joined the school, always the start "
                          "of an academic year."),
    ],
    notes=[
        "Guardians usually share a surname with the pupil, because Spanish "
        "children take the father's first surname. A guardian-matching "
        "heuristic can be tested against this and will find the roughly 20% "
        "of cases where it does not hold.",
    ],
)

ENROLLMENTS = Entity(
    name="enrollments",
    topic="education",
    grain="One row per pupil enrolled on one course.",
    description=(
        "Which pupils take which courses, and how they did. The final grade "
        "here is exactly the weighted sum of that enrolment's rows in the "
        "grades table."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("student_id", "integer", references="students.id", example=42,
              description="Who is enrolled. A pupil takes several courses in "
                          "a year, so this column is far from unique."),
        Field("course_id", "integer", references="courses.id", example=7,
              description="Which course. Always one at the pupil's own school "
                          "and matching their stage and year level."),
        Field("enrolled_on", "date", example="2024-09-09",
              description="Date the enrolment began, always in the September "
                          "the academic year started."),
        Field("status", "enum", values=sorted(ENROLLMENT_STATUSES), example="completed",
              description="How the enrolment ended. Withdrawn pupils left "
                          "part way through; 'repeated' marks a pupil retaking "
                          "a year, which Spanish schools do more often than "
                          "most European systems."),
        Field("final_grade", "decimal", unit="points (0-10)", nullable=True,
              example=7.40,
              description="Final mark on the Spanish 0-10 scale, where 5 is a "
                          "pass. Exactly the weighted sum of this enrolment's "
                          "assessment rows in the grades table, rounded to two "
                          "decimals. Empty while a course is still in progress."),
        Field("grade_band", "enum",
              values=["Suspenso", "Aprobado", "Bien", "Notable", "Sobresaliente"],
              nullable=True, example="Notable",
              description="The named band the final grade falls into, as "
                          "printed on a Spanish report card: Suspenso below 5, "
                          "then Aprobado, Bien, Notable and Sobresaliente. "
                          "Derived from final_grade, so the two always agree."),
        Field("attendance_rate", "decimal", unit="fraction", nullable=True,
              example=0.92,
              description="Proportion of recorded sessions the pupil attended, "
                          "computed from their rows in the attendance table. "
                          "Empty where no attendance was recorded. This is the "
                          "column that correlates with final_grade."),
    ],
    notes=[
        "This is the table to use for demonstrating analysis. Attendance and "
        "final grade are genuinely correlated, because both are driven by a "
        "hidden per-pupil diligence factor that is never stored. Plot one "
        "against the other and a real relationship appears, with realistic "
        "scatter -- something random data cannot give you.",
        "`final_grade` is exactly the weighted sum of the enrolment's rows in "
        "`grades`, whose weights sum to 1.00. Recomputing it yourself is a "
        "ready-made exercise, and CI checks the answer.",
        "A WARNING WORTH READING IF YOUR RECOMPUTATION DISAGREES. These "
        "grades are computed with exact decimal arithmetic, not floating "
        "point. Enrolment 2 has components 7.3x0.35 + 7.6x0.35 + 5.6x0.30, "
        "which is exactly 6.895 and rounds to 6.90. Ask SQLite for "
        "ROUND(SUM(score*weight), 2) and you get 6.89, because 6.895 cannot "
        "be represented exactly in binary and is stored as 6.89499... This "
        "is not an error in the data; it is the classic floating-point "
        "rounding trap, and this column is a good place to meet it.",
    ],
)

GRADES = Entity(
    name="grades",
    topic="education",
    grain="One row per assessment component of one enrolment.",
    description=(
        "The individual marks that make up a final grade: exams, coursework, "
        "practicals and participation. The weights within one enrolment "
        "always sum to exactly 1.00."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("enrollment_id", "integer", references="enrollments.id", example=42,
              description="Which enrolment this mark belongs to. Grouping by "
                          "this column and summing score times weight "
                          "reproduces the enrolment's final grade."),
        Field("assessment_type", "enum", values=sorted(ASSESSMENT_TYPES), example="exam",
              description="What was assessed. Exams carry the heaviest weight, "
                          "participation the lightest, which is how a Spanish "
                          "secondary course is typically structured."),
        Field("title", "string", example="Examen 2º trimestre",
              description="Name of the assessment as the pupil would see it, "
                          "usually naming the term it belonged to -- Spanish "
                          "courses run in three trimesters."),
        Field("score", "decimal", unit="points (0-10)", example=7.80,
              description="Mark awarded on the Spanish 0-10 scale, to one "
                          "decimal place, where 5 is a pass."),
        Field("weight", "decimal", unit="fraction", example=0.40,
              description="How much this component contributes to the final "
                          "grade. All the weights within one enrolment sum to "
                          "exactly 1.00, which CI verifies."),
        Field("graded_on", "date", example="2025-03-21",
              description="Date the mark was recorded, always during the "
                          "academic year the course ran in."),
    ],
)

ATTENDANCE = Entity(
    name="attendance",
    topic="education",
    grain="One row per pupil per recorded teaching session.",
    description=(
        "Session-by-session attendance. This is a sample of sessions rather "
        "than every one of them, which keeps the table a sensible size while "
        "still supporting a meaningful attendance rate per enrolment."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("enrollment_id", "integer", references="enrollments.id", example=42,
              description="Which pupil-on-which-course this record is for. "
                          "Counting present rows against total rows per "
                          "enrolment gives that enrolment's attendance rate."),
        Field("session_date", "date", example="2025-02-11",
              description="Date of the session. Always a weekday during term "
                          "time -- Spanish schools do not teach at weekends or "
                          "through July and August."),
        Field("status", "enum", values=sorted(ATTENDANCE_STATUSES), example="present",
              description="Whether the pupil attended. 'excused' covers an "
                          "absence the school accepted in advance, which is "
                          "counted separately from an unexplained one in "
                          "Spanish attendance reporting."),
        Field("minutes_late", "integer", unit="minutes", example=0,
              description="How late the pupil arrived, zero unless the status "
                          "is 'late'. Typically between 5 and 35 minutes when "
                          "it is not."),
    ],
)

EXAMS = Entity(
    name="exams",
    topic="education",
    grain="One row per scheduled examination sitting.",
    description=(
        "Timetabled exams, each placed in a room at a time. Useful for "
        "testing scheduling features and room-clash detection, since the "
        "same room is used many times."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("course_id", "integer", references="courses.id", example=7,
              description="Which course is being examined. A course typically "
                          "has a midterm and a final, sometimes a resit."),
        Field("classroom_id", "integer", references="classrooms.id", example=12,
              description="Where the exam takes place. Always a room at the "
                          "same school as the course."),
        Field("exam_date", "date", example="2025-06-05",
              description="Date of the sitting, always a weekday during term "
                          "time and within the course's academic year."),
        Field("exam_type", "enum", values=sorted(EXAM_TYPES), example="final",
              description="Which kind of sitting: a midterm, the final, a "
                          "practice mock, or a resit for pupils who failed "
                          "first time."),
        Field("duration_minutes", "integer", unit="minutes", example=90,
              description="How long pupils get, from 45 minutes for a short "
                          "midterm to 180 for a Bachillerato final."),
        Field("max_score", "decimal", unit="points", example=10.00,
              description="Marks available. Almost always 10, because the "
                          "Spanish scale is 0 to 10, which makes the few "
                          "exceptions worth handling."),
        Field("registered_students", "integer", unit="students", example=28,
              description="How many pupils were entered for this sitting, "
                          "never more than the capacity of the room it was "
                          "scheduled into."),
    ],
)


# ===========================================================================
# PART 3 -- THE GENERATOR
# ===========================================================================

def _strip_accents(text: str) -> str:
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _email_from_name(full_name: str, domain: str, rng: Rng) -> str:
    parts = [part.lower() for part in _strip_accents(full_name).split() if part]
    stem = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
    suffix = "" if rng.python.random() > 0.08 else str(rng.python.randint(2, 9))
    return f"{stem}{suffix}@{domain}"


def _academic_year_span(academic_year: str) -> tuple[date, date]:
    """"2024/2025" -> (2024-09-09, 2025-06-20). Spanish terms, roughly."""
    start_year = int(academic_year.split("/")[0])
    return date(start_year, 9, 9), date(start_year + 1, 6, 20)


def _generate_schools(count: int) -> list[dict[str, Any]]:
    rng = Rng("education", "schools")

    # Spanish schools are named after writers, saints and places.
    dedications = [
        "Miguel de Unamuno", "Rosalía de Castro", "Antonio Machado",
        "Santa Teresa", "Juan Ramón Jiménez", "Federico García Lorca",
        "San Isidoro", "Emilia Pardo Bazán", "Ramón y Cajal", "Gloria Fuertes",
        "Concepción Arenal", "Luis Vives", "Blas de Otero", "Clara Campoamor",
    ]
    capacity_by_type = {"CEIP": (420, 110), "IES": (880, 220),
                        "Concertado": (640, 160), "Privado": (520, 140)}

    rows = []
    used_names: set[str] = set()
    used_codes: set[str] = set()

    for index in range(1, count + 1):
        school_type = rng.weighted_choice(SCHOOL_TYPES)
        location = generate_address(rng, with_phone=True)

        name = f"{school_type} {rng.python.choice(dedications)}"
        while name in used_names:
            name = f"{school_type} {rng.python.choice(dedications)}"
        used_names.add(name)

        # Centre code: province code then a six-digit centre number, the
        # shape Spanish education authorities use.
        province_code = location["postal_code"][:2]
        code = f"{province_code}{rng.python.randint(0, 999_999):06d}"
        while code in used_codes:
            code = f"{province_code}{rng.python.randint(0, 999_999):06d}"
        used_codes.add(code)

        mean, sd = capacity_by_type[school_type]
        rows.append({
            "id": index,
            "code": code,
            "name": name,
            "type": school_type,
            "city": location["city"],
            "province": location["province"],
            "address": location["address"],
            "postal_code": location["postal_code"],
            "phone": location["phone"],
            "student_capacity": int(max(120, rng.numpy.normal(mean, sd))),
            "founded": rng.python.randint(1900, 2018),
        })
    return rows


def _generate_classrooms(schools: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("education", "classrooms")

    room_types = {"standard": 66, "laboratory": 9, "computer_lab": 9,
                  "workshop": 6, "gym": 5, "music": 5}

    rows: list[dict[str, Any]] = []
    per_school = max(1, count // max(1, len(schools)))

    for school in schools:
        buildings = ["Edificio A"] if school["student_capacity"] < 500 else [
            "Edificio A", "Edificio B"
        ]
        for _ in range(per_school):
            if len(rows) >= count:
                return rows
            building = rng.python.choice(buildings)
            floor = rng.python.randint(0, 3)
            room_type = rng.weighted_choice(room_types)

            # Specialist rooms are smaller than standard classrooms.
            capacity = (
                rng.python.randint(15, 24) if room_type in ("laboratory", "computer_lab", "music")
                else rng.python.randint(24, 40)
            )

            rows.append({
                "id": len(rows) + 1,
                "school_id": school["id"],
                "room_code": f"{building[-1]}-{floor}{rng.python.randint(1, 20):02d}",
                "building": building,
                "floor": floor,
                "capacity": capacity,
                "room_type": room_type,
            })
    return rows


def _generate_teachers(schools: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("education", "teachers")

    rows = []
    for index in range(1, count + 1):
        school = rng.python.choice(schools)
        is_female = rng.python.random() < 0.66  # Spanish teaching skews female
        full_name = rng.faker.name_female() if is_female else rng.faker.name_male()

        # Primary teachers hold a different qualification from secondary ones.
        if school["type"] == "CEIP":
            qualification = rng.weighted_choice({
                "Grado en Educación Primaria": 78,
                "Licenciatura + CAP": 14,
                "Doctorado": 3,
                "Grado + Máster en Formación del Profesorado": 5,
            })
        else:
            qualification = rng.weighted_choice(QUALIFICATIONS)

        # Spanish teaching contracts start with the academic year.
        hire_year = rng.python.randint(max(1985, school["founded"]), 2024)
        rows.append({
            "id": index,
            "school_id": school["id"],
            "teacher_code": f"PRF-{index:05d}",
            "full_name": full_name,
            "national_id": dni(rng),
            "department": rng.python.choice(DEPARTMENTS),
            "email": _email_from_name(full_name, "example.org", rng),
            "qualification": qualification,
            "contract_type": rng.weighted_choice(CONTRACT_TYPES),
            "hired_at": date(hire_year, 9, 1),
        })
    return rows


def _generate_courses(
    schools: list[dict], teachers: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("education", "courses")

    teachers_by_school: dict[int, list[dict]] = {}
    for teacher in teachers:
        teachers_by_school.setdefault(teacher["school_id"], []).append(teacher)

    hours_by_subject_weight = {5: 12, 4: 26, 3: 32, 2: 20, 1: 10}

    rows = []
    used_codes: set[str] = set()

    for index in range(1, count + 1):
        school = rng.python.choice(schools)
        staff = teachers_by_school.get(school["id"])
        if not staff:
            continue

        # A school only teaches the stages its type covers.
        stage = rng.python.choice(STAGES_BY_SCHOOL_TYPE[school["type"]])
        _, _, years = STAGES[stage]
        title = rng.python.choice(SUBJECTS[stage])

        # Course code: three letters from the subject, then a sequence.
        letters = _strip_accents(title).upper().replace(" ", "")[:3] or "GEN"
        code = f"{letters}-{index:05d}"
        while code in used_codes:
            code = f"{letters}-{rng.python.randint(1, 99999):05d}"
        used_codes.add(code)

        rows.append({
            "id": index,
            "school_id": school["id"],
            "teacher_id": rng.python.choice(staff)["id"],
            "code": code,
            "title": title,
            "stage": stage,
            "year_level": rng.python.randint(1, years),
            "academic_year": rng.python.choice(ACADEMIC_YEARS),
            "hours_per_week": rng.weighted_choice(hours_by_subject_weight),
        })
    return rows


def _generate_students(schools: list[dict], count: int) -> list[dict[str, Any]]:
    """Generate pupils, each carrying a hidden diligence factor.

    THE DILIGENCE FACTOR IS THE POINT OF THIS TOPIC.

    Every pupil gets a value between roughly 0.25 and 1.0 which is never
    written to any file. It drives two separate things later: how likely
    they are to be marked present, and how well they score. Because both
    flow from the same hidden cause, attendance and achievement end up
    genuinely correlated in the published data -- without either column
    being computed from the other.

    That is what makes this dataset usable for demonstrating analysis.
    Random data has no relationship to find, so every chart drawn on it
    looks like static and every model trained on it learns nothing.
    """
    rng = Rng("education", "students")

    # Stages a school actually teaches, so a pupil's age fits the centre.
    rows = []
    for index in range(1, count + 1):
        school = rng.python.choice(schools)
        stage = rng.python.choice(STAGES_BY_SCHOOL_TYPE[school["type"]])
        age_low, age_high, years = STAGES[stage]

        year_level = rng.python.randint(1, years)
        # Age follows from the stage and the year within it.
        age = age_low + year_level - 1 + rng.python.choice([0, 0, 0, 1])
        age = min(age, age_high)

        birth_date = date(PERIOD_END.year - age, 1, 1) + timedelta(
            days=rng.python.randint(0, 364)
        )

        sex = rng.python.choice(["F", "M"])
        full_name = rng.faker.name_female() if sex == "F" else rng.faker.name_male()

        # The guardian usually shares the pupil's first surname, because
        # Spanish children take the father's first surname.
        name_parts = full_name.split()
        if len(name_parts) >= 2 and rng.python.random() < 0.80:
            guardian_given = (
                rng.faker.first_name_male() if rng.python.random() < 0.5
                else rng.faker.first_name_female()
            )
            guardian_name = f"{guardian_given} {name_parts[1]} {rng.faker.last_name()}"
        else:
            guardian_name = rng.faker.name()

        location = generate_address(rng, with_phone=True, mobile=True)

        rows.append({
            "id": index,
            "school_id": school["id"],
            "student_code": f"ALU-{index:06d}",
            "full_name": full_name,
            "birth_date": birth_date,
            "sex": sex,
            "stage": stage,
            "year_level": year_level,
            "guardian_name": guardian_name,
            "guardian_phone": location["phone"],
            "guardian_email": rng.maybe_null(
                _email_from_name(guardian_name, "example.com", rng), 0.14
            ),
            "enrolled_on": date(
                rng.python.choice([2022, 2023, 2024]), 9, rng.python.randint(9, 15)
            ),
            # NOT written to any file -- see the docstring above.
            "_diligence": min(1.0, max(0.25, rng.numpy.normal(0.78, 0.17))),
        })
    return rows


def _generate_enrollments(
    students: list[dict], courses: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("education", "enrollments")

    # A pupil can only take courses at their own school, stage and year.
    courses_by_key: dict[tuple, list[dict]] = {}
    for course in courses:
        key = (course["school_id"], course["stage"], course["year_level"])
        courses_by_key.setdefault(key, []).append(course)

    rows: list[dict[str, Any]] = []
    for student in students:
        if len(rows) >= count:
            break
        key = (student["school_id"], student["stage"], student["year_level"])
        available = courses_by_key.get(key, [])
        if not available:
            continue

        how_many = min(len(available), rng.python.randint(2, 5))
        for course in rng.python.sample(available, how_many):
            if len(rows) >= count:
                break
            term_start, _ = _academic_year_span(course["academic_year"])

            rows.append({
                "id": len(rows) + 1,
                "student_id": student["id"],
                "course_id": course["id"],
                "enrolled_on": term_start,
                "status": rng.weighted_choice(ENROLLMENT_STATUSES),
                # Filled in once grades and attendance exist.
                "final_grade": None,
                "grade_band": None,
                "attendance_rate": None,
                "_diligence": student["_diligence"],
                "_academic_year": course["academic_year"],
            })
    return rows


def _generate_attendance(enrollments: list[dict], count: int) -> list[dict[str, Any]]:
    """Sample teaching sessions, with presence driven by hidden diligence."""
    rng = Rng("education", "attendance")

    rows: list[dict[str, Any]] = []
    for enrollment in enrollments:
        if len(rows) >= count:
            break
        term_start, term_end = _academic_year_span(enrollment["_academic_year"])
        diligence = enrollment["_diligence"]

        for _ in range(SESSIONS_PER_ENROLLMENT):
            if len(rows) >= count:
                break
            session_date = next_weekday(rng.date_between(term_start, term_end))
            if session_date > term_end:
                continue

            # A diligent pupil is present far more often. The mapping is
            # deliberately not linear: even a poor attender turns up most
            # days, which is what real attendance data looks like.
            present_probability = 0.55 + 0.42 * diligence
            draw = rng.python.random()

            if draw < present_probability:
                status, minutes_late = "present", 0
            elif draw < present_probability + 0.06:
                status, minutes_late = "late", rng.python.randint(5, 35)
            elif draw < present_probability + 0.09:
                status, minutes_late = "excused", 0
            else:
                status, minutes_late = "absent", 0

            rows.append({
                "id": len(rows) + 1,
                "enrollment_id": enrollment["id"],
                "session_date": session_date,
                "status": status,
                "minutes_late": minutes_late,
            })
    return rows


def _generate_grades(enrollments: list[dict], count: int) -> list[dict[str, Any]]:
    """Assessment components whose weights sum to exactly 1.00.

    Rounding each weight independently would leave them summing to 0.99 or
    1.01, and the final grade would then disagree with the components. The
    last weight therefore absorbs the rounding remainder.
    """
    rng = Rng("education", "grades")

    # (types, weights) templates. Weights sum to 1.00 by construction.
    templates = [
        (["exam", "coursework", "participation"], [Decimal("0.60"), Decimal("0.30"), Decimal("0.10")]),
        (["exam", "exam", "coursework"], [Decimal("0.35"), Decimal("0.35"), Decimal("0.30")]),
        (["exam", "practical", "coursework", "participation"],
         [Decimal("0.40"), Decimal("0.25"), Decimal("0.25"), Decimal("0.10")]),
        (["exam", "coursework"], [Decimal("0.70"), Decimal("0.30")]),
    ]
    term_names = ["1º trimestre", "2º trimestre", "3º trimestre"]

    rows: list[dict[str, Any]] = []
    for enrollment in enrollments:
        if len(rows) >= count:
            break
        types, weights = rng.python.choice(templates)
        term_start, term_end = _academic_year_span(enrollment["_academic_year"])
        diligence = enrollment["_diligence"]

        # The hidden diligence factor drives the score, exactly as it drives
        # attendance -- which is what creates the correlation between them.
        #
        # The constants are tuned so that roughly a fifth of final grades
        # fall below 5 (suspenso), which is what Spanish secondary schools
        # actually report. An earlier, more generous setting produced only
        # 4% failures and made the whole distribution look implausible.
        centre = 0.8 + 7.2 * diligence

        for position, (assessment_type, weight) in enumerate(zip(types, weights)):
            if len(rows) >= count:
                break
            score = float(rng.numpy.normal(centre, 1.6))
            score = round(min(10.0, max(0.0, score)), 1)

            rows.append({
                "id": len(rows) + 1,
                "enrollment_id": enrollment["id"],
                "assessment_type": assessment_type,
                "title": (
                    f"{'Examen' if assessment_type == 'exam' else 'Trabajo'} "
                    f"{term_names[position % 3]}"
                ),
                "score": Decimal(str(score)).quantize(Decimal("0.01")),
                "weight": weight,
                "graded_on": rng.date_between(term_start, term_end),
            })
    return rows


def _finalise_enrollments(
    enrollments: list[dict], grades: list[dict], attendance: list[dict]
) -> None:
    """Compute final_grade, grade_band and attendance_rate from the raw rows.

    Derived columns are computed from the data that was actually generated,
    never alongside it. That is what guarantees they agree: there is only
    one source of truth and the derived value is read from it.
    """
    grades_by_enrollment: dict[int, list[dict]] = {}
    for grade in grades:
        grades_by_enrollment.setdefault(grade["enrollment_id"], []).append(grade)

    attendance_by_enrollment: dict[int, list[dict]] = {}
    for record in attendance:
        attendance_by_enrollment.setdefault(record["enrollment_id"], []).append(record)

    for enrollment in enrollments:
        components = grades_by_enrollment.get(enrollment["id"], [])
        if components and enrollment["status"] != "in_progress":
            weighted = sum(
                Decimal(str(row["score"])) * Decimal(str(row["weight"]))
                for row in components
            )
            final = weighted.quantize(Decimal("0.01"))
            enrollment["final_grade"] = final
            enrollment["grade_band"] = grade_band(float(final))

        sessions = attendance_by_enrollment.get(enrollment["id"], [])
        if sessions:
            # "Late" still counts as attending -- which is how schools
            # actually report it, and a distinction worth getting right.
            attended = sum(1 for row in sessions if row["status"] in ("present", "late"))
            enrollment["attendance_rate"] = Decimal(
                str(round(attended / len(sessions), 2))
            )


def _generate_exams(
    courses: list[dict], classrooms: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("education", "exams")

    rooms_by_school: dict[int, list[dict]] = {}
    for room in classrooms:
        rooms_by_school.setdefault(room["school_id"], []).append(room)

    rows = []
    for index in range(1, count + 1):
        course = rng.python.choice(courses)
        rooms = rooms_by_school.get(course["school_id"])
        if not rooms:
            continue
        room = rng.python.choice(rooms)

        term_start, term_end = _academic_year_span(course["academic_year"])
        exam_date = next_weekday(rng.date_between(term_start, term_end))
        if exam_date > term_end:
            exam_date = term_end

        exam_type = rng.weighted_choice(EXAM_TYPES)
        # Bachillerato finals are longer than a primary midterm.
        if course["stage"] == "Bachillerato" and exam_type == "final":
            duration = rng.python.choice([120, 150, 180])
        elif exam_type in ("midterm", "mock"):
            duration = rng.python.choice([45, 60, 90])
        else:
            duration = rng.python.choice([60, 90, 120])

        rows.append({
            "id": index,
            "course_id": course["id"],
            "classroom_id": room["id"],
            "exam_date": exam_date,
            "exam_type": exam_type,
            "duration_minutes": duration,
            "max_score": Decimal("10.00"),
            # Never more pupils than the room can seat.
            "registered_students": rng.python.randint(
                max(5, room["capacity"] // 3), room["capacity"]
            ),
        })
    return rows


def generate(scale: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    """Produce every table in the education topic."""
    counts = {name: max(1, int(number * scale)) for name, number in DEFAULT_COUNTS.items()}

    schools = _generate_schools(counts["schools"])
    classrooms = _generate_classrooms(schools, counts["classrooms"])
    teachers = _generate_teachers(schools, counts["teachers"])
    courses = _generate_courses(schools, teachers, counts["courses"])
    students = _generate_students(schools, counts["students"])
    enrollments = _generate_enrollments(students, courses, counts["enrollments"])
    attendance = _generate_attendance(enrollments, counts["attendance"])
    grades = _generate_grades(enrollments, counts["grades"])
    exams = _generate_exams(courses, classrooms, counts["exams"])

    # Derive the enrolment summary columns from the rows just generated.
    _finalise_enrollments(enrollments, grades, attendance)

    # Strip the hidden helper fields. They exist only to create the
    # correlation between attendance and achievement and must never be
    # published -- if they were, the relationship would stop being
    # something you have to discover in the data.
    for row in students:
        row.pop("_diligence", None)
    for row in enrollments:
        row.pop("_diligence", None)
        row.pop("_academic_year", None)

    return {
        "schools": schools,
        "classrooms": classrooms,
        "teachers": teachers,
        "courses": courses,
        "students": students,
        "enrollments": enrollments,
        "grades": grades,
        "attendance": attendance,
        "exams": exams,
    }


TOPIC = Topic(
    name="education",
    title="Education / Schools",
    summary=(
        "Spanish schools, pupils, courses and gradebooks on the 0-10 scale, "
        "with attendance that genuinely correlates with achievement."
    ),
    description=(
        "A Spanish school system: state and private centres across Primaria, "
        "ESO, Bachillerato and FP, with three academic years of enrolments, "
        "grades and attendance.\n\n"
        "This is the topic to reach for when you need data with something in "
        "it to FIND. Every pupil carries a hidden diligence factor that "
        "drives both how often they attend and how well they score, and that "
        "factor is never published -- so the correlation between attendance "
        "and achievement is genuinely emergent rather than computed. Plot one "
        "against the other and a real relationship appears, with realistic "
        "scatter. Random data gives you nothing to discover.\n\n"
        "Grades use the Spanish 0-10 scale where 5 is a pass, with the named "
        "bands a report card actually prints. Assessment weights within an "
        "enrolment sum to exactly 1.00 and the final grade is exactly that "
        "weighted sum."
    ),
    entities=[
        SCHOOLS,
        CLASSROOMS,
        TEACHERS,
        COURSES,
        STUDENTS,
        ENROLLMENTS,
        GRADES,
        ATTENDANCE,
        EXAMS,
    ],
)
