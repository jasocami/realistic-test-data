"""
Find the relationship hidden in the education data.

    python docs/examples/08_find_the_signal.py

Every pupil carries a diligence factor that drives BOTH how often they
attend and how well they score -- and it is never published. So the
correlation below is genuinely emergent: you are discovering it in the data,
not reading back a column that was computed from another one.

This is what makes the dataset useful for demonstrating analysis. Random
data has nothing to find, and every chart drawn on it looks like static.
"""

import sqlite3
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATABASE = REPO_ROOT / "db" / "education" / "education.sqlite"


def correlation(xs: list[float], ys: list[float]) -> float:
    """Pearson's r, computed by hand so there is no numpy dependency."""
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
    return covariance / (statistics.pstdev(xs) * statistics.pstdev(ys))


def main() -> None:
    connection = sqlite3.connect(DATABASE)
    rows = connection.execute("""
        SELECT attendance_rate, final_grade
        FROM enrollments
        WHERE attendance_rate IS NOT NULL AND final_grade IS NOT NULL
    """).fetchall()
    connection.close()

    attendance = [float(a) for a, _ in rows]
    grades = [float(g) for _, g in rows]

    print(f"{len(rows):,} enrolments with both an attendance rate and a grade\n")
    print(f"  correlation(attendance, grade) = {correlation(attendance, grades):.3f}")
    print(f"  mean grade overall             = {statistics.mean(grades):.2f} / 10\n")

    # Group into attendance bands and show the gradient.
    bands = [(0.0, 0.7, "under 70%"), (0.7, 0.8, "70-80%"),
             (0.8, 0.9, "80-90%"), (0.9, 1.01, "90-100%")]

    print("  attendance      pupils   mean grade")
    print("  " + "-" * 38)
    for low, high, label in bands:
        in_band = [g for a, g in zip(attendance, grades) if low <= a < high]
        if not in_band:
            continue
        bar = "█" * int(statistics.mean(in_band) * 3)
        print(f"  {label:<14} {len(in_band):>6}   "
              f"{statistics.mean(in_band):>5.2f}  {bar}")

    print("\n  Attendance was never used to compute a grade. Both follow from")
    print("  a hidden per-pupil factor -- see _generate_students() in")
    print("  generators/topics/education.py.")


if __name__ == "__main__":
    main()
