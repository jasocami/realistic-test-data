-- education/schema.sql
-- Table structure for the 'education' topic. No data -- see
-- education.sql.gz for the rows, or education.sqlite for a
-- database you can query immediately.
--
-- SYNTHETIC DATA -- every record is invented. See README.md.

PRAGMA foreign_keys = ON;

-- schools: One row per school centre in the network.
CREATE TABLE "schools" (
    "id" INTEGER PRIMARY KEY,
    "code" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL UNIQUE,
    "type" TEXT NOT NULL CHECK ("type" IN ('CEIP', 'Concertado', 'IES', 'Privado')),
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "address" TEXT NOT NULL,
    "postal_code" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "student_capacity" INTEGER NOT NULL,
    "founded" INTEGER NOT NULL
);

-- classrooms: One row per teaching room in one school.
CREATE TABLE "classrooms" (
    "id" INTEGER PRIMARY KEY,
    "school_id" INTEGER NOT NULL,
    "room_code" TEXT NOT NULL,
    "building" TEXT NOT NULL,
    "floor" INTEGER NOT NULL,
    "capacity" INTEGER NOT NULL,
    "room_type" TEXT NOT NULL CHECK ("room_type" IN ('standard', 'laboratory', 'computer_lab', 'workshop', 'gym', 'music')),
    FOREIGN KEY ("school_id") REFERENCES "schools" ("id")
);
CREATE INDEX "idx_classrooms_school_id" ON "classrooms" ("school_id");

-- teachers: One row per member of teaching staff.
CREATE TABLE "teachers" (
    "id" INTEGER PRIMARY KEY,
    "school_id" INTEGER NOT NULL,
    "teacher_code" TEXT NOT NULL UNIQUE,
    "full_name" TEXT NOT NULL,
    "national_id" TEXT NOT NULL UNIQUE,
    "department" TEXT NOT NULL CHECK ("department" IN ('Artes', 'Ciencias', 'Ciencias Sociales', 'Educación Física', 'Formación Profesional', 'Idiomas', 'Lengua y Literatura', 'Matemáticas', 'Orientación', 'Tecnología')),
    "email" TEXT NOT NULL,
    "qualification" TEXT NOT NULL CHECK ("qualification" IN ('Doctorado', 'Grado + Máster en Formación del Profesorado', 'Grado en Educación Primaria', 'Licenciatura + CAP', 'Técnico Superior FP')),
    "contract_type" TEXT NOT NULL CHECK ("contract_type" IN ('interim', 'permanent', 'temporary')),
    "hired_at" TEXT NOT NULL,
    FOREIGN KEY ("school_id") REFERENCES "schools" ("id")
);
CREATE INDEX "idx_teachers_school_id" ON "teachers" ("school_id");

-- courses: One row per course taught in one academic year.
CREATE TABLE "courses" (
    "id" INTEGER PRIMARY KEY,
    "school_id" INTEGER NOT NULL,
    "teacher_id" INTEGER NOT NULL,
    "code" TEXT NOT NULL UNIQUE,
    "title" TEXT NOT NULL,
    "stage" TEXT NOT NULL CHECK ("stage" IN ('Bachillerato', 'ESO', 'FP', 'Primaria')),
    "year_level" INTEGER NOT NULL,
    "academic_year" TEXT NOT NULL CHECK ("academic_year" IN ('2022/2023', '2023/2024', '2024/2025')),
    "hours_per_week" INTEGER NOT NULL,
    FOREIGN KEY ("school_id") REFERENCES "schools" ("id"),
    FOREIGN KEY ("teacher_id") REFERENCES "teachers" ("id")
);
CREATE INDEX "idx_courses_school_id" ON "courses" ("school_id");
CREATE INDEX "idx_courses_teacher_id" ON "courses" ("teacher_id");

-- students: One row per enrolled pupil.
CREATE TABLE "students" (
    "id" INTEGER PRIMARY KEY,
    "school_id" INTEGER NOT NULL,
    "student_code" TEXT NOT NULL UNIQUE,
    "full_name" TEXT NOT NULL,
    "birth_date" TEXT NOT NULL,
    "sex" TEXT NOT NULL CHECK ("sex" IN ('F', 'M')),
    "stage" TEXT NOT NULL CHECK ("stage" IN ('Bachillerato', 'ESO', 'FP', 'Primaria')),
    "year_level" INTEGER NOT NULL,
    "guardian_name" TEXT NOT NULL,
    "guardian_phone" TEXT NOT NULL,
    "guardian_email" TEXT,
    "enrolled_on" TEXT NOT NULL,
    FOREIGN KEY ("school_id") REFERENCES "schools" ("id")
);
CREATE INDEX "idx_students_school_id" ON "students" ("school_id");

-- enrollments: One row per pupil enrolled on one course.
CREATE TABLE "enrollments" (
    "id" INTEGER PRIMARY KEY,
    "student_id" INTEGER NOT NULL,
    "course_id" INTEGER NOT NULL,
    "enrolled_on" TEXT NOT NULL,
    "status" TEXT NOT NULL CHECK ("status" IN ('completed', 'in_progress', 'repeated', 'withdrawn')),
    "final_grade" REAL,
    "grade_band" TEXT CHECK ("grade_band" IN ('Suspenso', 'Aprobado', 'Bien', 'Notable', 'Sobresaliente')),
    "attendance_rate" REAL,
    FOREIGN KEY ("student_id") REFERENCES "students" ("id"),
    FOREIGN KEY ("course_id") REFERENCES "courses" ("id")
);
CREATE INDEX "idx_enrollments_student_id" ON "enrollments" ("student_id");
CREATE INDEX "idx_enrollments_course_id" ON "enrollments" ("course_id");

-- grades: One row per assessment component of one enrolment.
CREATE TABLE "grades" (
    "id" INTEGER PRIMARY KEY,
    "enrollment_id" INTEGER NOT NULL,
    "assessment_type" TEXT NOT NULL CHECK ("assessment_type" IN ('coursework', 'exam', 'participation', 'practical')),
    "title" TEXT NOT NULL,
    "score" REAL NOT NULL,
    "weight" REAL NOT NULL,
    "graded_on" TEXT NOT NULL,
    FOREIGN KEY ("enrollment_id") REFERENCES "enrollments" ("id")
);
CREATE INDEX "idx_grades_enrollment_id" ON "grades" ("enrollment_id");

-- attendance: One row per pupil per recorded teaching session.
CREATE TABLE "attendance" (
    "id" INTEGER PRIMARY KEY,
    "enrollment_id" INTEGER NOT NULL,
    "session_date" TEXT NOT NULL,
    "status" TEXT NOT NULL CHECK ("status" IN ('absent', 'excused', 'late', 'present')),
    "minutes_late" INTEGER NOT NULL,
    FOREIGN KEY ("enrollment_id") REFERENCES "enrollments" ("id")
);
CREATE INDEX "idx_attendance_enrollment_id" ON "attendance" ("enrollment_id");

-- exams: One row per scheduled examination sitting.
CREATE TABLE "exams" (
    "id" INTEGER PRIMARY KEY,
    "course_id" INTEGER NOT NULL,
    "classroom_id" INTEGER NOT NULL,
    "exam_date" TEXT NOT NULL,
    "exam_type" TEXT NOT NULL CHECK ("exam_type" IN ('final', 'midterm', 'mock', 'resit')),
    "duration_minutes" INTEGER NOT NULL,
    "max_score" REAL NOT NULL,
    "registered_students" INTEGER NOT NULL,
    FOREIGN KEY ("course_id") REFERENCES "courses" ("id"),
    FOREIGN KEY ("classroom_id") REFERENCES "classrooms" ("id")
);
CREATE INDEX "idx_exams_course_id" ON "exams" ("course_id");
CREATE INDEX "idx_exams_classroom_id" ON "exams" ("classroom_id");
