"""Crea la base de datos y carga los ejercicios y rutinas base (idempotente)."""
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE.parent / "data" / "calistenia.db"

# nombre, categoría, medición, por_lado
EXERCISES = [
    ("Dominadas",                    "traccion", "reps",   0),
    ("Dominadas supinas",            "traccion", "reps",   0),
    ("Remo invertido",               "traccion", "reps",   0),
    ("Flexiones",                    "empuje",   "reps",   0),
    ("Flexiones diamante",           "empuje",   "reps",   0),
    ("Fondos en paralelas",          "empuje",   "reps",   0),
    ("Pike push-up",                 "empuje",   "reps",   0),
    ("Sentadilla búlgara",           "piernas",  "reps",   1),
    ("Sentadilla",                   "piernas",  "reps",   0),
    ("Puente de glúteos a una pierna","piernas", "reps",   1),
    ("Plancha",                      "core",     "tiempo", 0),
    ("L-sit",                        "core",     "tiempo", 0),
    ("Elevación de piernas colgado", "core",     "reps",   0),
]

# nombre rutina, día (0 = lunes), notas
ROUTINES = [
    ("Lunes - Fuerza",        0, "Pocas reps, más dificultad"),
    ("Miércoles - Hipertrofia", 2, "Rango medio de reps, control del movimiento"),
]

# rutina, ejercicio, orden, series, reps_min, reps_max, segundos, descanso
ROUTINE_EXERCISES = [
    ("Lunes - Fuerza", "Dominadas",           1, 4, 4, 6,  None, 150),
    ("Lunes - Fuerza", "Fondos en paralelas", 2, 4, 5, 8,  None, 150),
    ("Lunes - Fuerza", "Flexiones",           3, 3, 8, 12, None, 90),
    ("Lunes - Fuerza", "Plancha",             4, 3, None, None, 45, 60),
    ("Miércoles - Hipertrofia", "Dominadas",           1, 3, 6, 10, None, 120),
    ("Miércoles - Hipertrofia", "Fondos en paralelas", 2, 3, 8, 12, None, 120),
    ("Miércoles - Hipertrofia", "Flexiones diamante",  3, 3, 8, 15, None, 90),
    ("Miércoles - Hipertrofia", "Plancha",             4, 3, None, None, 60, 60),
]


def main() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))

    con.executemany(
        "INSERT OR IGNORE INTO exercises (name, category, measure_type, per_side) VALUES (?,?,?,?)",
        EXERCISES,
    )
    con.executemany(
        "INSERT OR IGNORE INTO routines (name, suggested_day, notes) VALUES (?,?,?)",
        ROUTINES,
    )
    for r, e, pos, sets, rmin, rmax, secs, rest in ROUTINE_EXERCISES:
        con.execute(
            """INSERT OR IGNORE INTO routine_exercises
               (routine_id, exercise_id, position, target_sets,
                target_reps_min, target_reps_max, target_seconds, rest_seconds)
               VALUES ((SELECT id FROM routines  WHERE name = ?),
                       (SELECT id FROM exercises WHERE name = ?), ?,?,?,?,?,?)""",
            (r, e, pos, sets, rmin, rmax, secs, rest),
        )
    con.commit()
    n_ex = con.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    n_ro = con.execute("SELECT COUNT(*) FROM routines").fetchone()[0]
    print(f"Listo: {n_ex} ejercicios, {n_ro} rutinas en {DB_PATH.name}")
    con.close()


if __name__ == "__main__":
    main()
