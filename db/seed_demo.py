"""Carga ~8 semanas de entrenamientos de ejemplo para ver gráficas reales.

Uso:  python db/seed_demo.py          (falla si ya hay sesiones)
      python db/seed_demo.py --force  (borra sesiones y pesos antes de cargar)
"""
import random
import sqlite3
import sys
from datetime import date, timedelta

import init_db


def seed_demo(con: sqlite3.Connection, weeks: int = 8, today: date | None = None) -> int:
    rng = random.Random(42)                       # mismos datos en cada ejecución
    today = today or date.today()
    first_monday = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    created = 0
    for wk in range(weeks):
        monday = first_monday + timedelta(weeks=wk)
        bodyweight = round(72.0 + 0.15 * wk, 1)
        con.execute("INSERT OR IGNORE INTO body_metrics (date, bodyweight_kg) VALUES (?,?)",
                    (monday.isoformat(), bodyweight))
        for routine, offset in (("Lunes - Fuerza", 0), ("Miércoles - Hipertrofia", 2)):
            day = monday + timedelta(days=offset)
            if day > today or rng.random() < 0.1:   # sin fechas futuras; algún día se falla
                continue
            rid = con.execute("SELECT id FROM routines WHERE name = ?", (routine,)).fetchone()[0]
            wid = con.execute(
                """INSERT INTO workouts (date, routine_id, bodyweight_kg, duration_seconds, feeling, finished)
                   VALUES (?,?,?,?,?,1)""",
                (day.isoformat(), rid, bodyweight, rng.randint(2400, 3600), rng.randint(3, 5)),
            ).lastrowid
            items = con.execute(
                """SELECT re.exercise_id, e.name, re.target_sets, re.target_reps_min,
                          re.target_reps_max, re.target_seconds
                   FROM routine_exercises re JOIN exercises e ON e.id = re.exercise_id
                   WHERE re.routine_id = ? ORDER BY re.position""", (rid,)).fetchall()
            for ex_id, name, n_sets, rmin, rmax, secs in items:
                n = 0
                if name == "Dominadas":              # una serie de calentamiento
                    n += 1
                    con.execute("INSERT INTO sets (workout_id, exercise_id, set_number, reps, is_warmup)"
                                " VALUES (?,?,?,?,1)", (wid, ex_id, n, max(rmin - 2, 1)))
                for i in range(n_sets):
                    n += 1
                    if rmin is None:                 # ejercicio por tiempo
                        con.execute("INSERT INTO sets (workout_id, exercise_id, set_number, seconds)"
                                    " VALUES (?,?,?,?)", (wid, ex_id, n, secs + 5 * wk - rng.randint(0, 5)))
                        continue
                    reps = min(rmin + wk // 2, rmax) - (i // 2) - rng.randint(0, 1)
                    extra = 2.5 if (name == "Dominadas" and wk >= weeks - 3) else 0
                    con.execute(
                        """INSERT INTO sets (workout_id, exercise_id, set_number, reps, extra_weight_kg)
                           VALUES (?,?,?,?,?)""", (wid, ex_id, n, max(reps, 1), extra))
            created += 1
    con.commit()
    return created


def main() -> None:
    init_db.main()                                    # crea la BD si no existe
    con = sqlite3.connect(init_db.DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    if con.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]:
        if "--force" not in sys.argv:
            sys.exit("Ya hay sesiones. Usa --force para reemplazarlas con los datos de ejemplo.")
        con.execute("DELETE FROM workouts")
        con.execute("DELETE FROM body_metrics")
    print(f"{seed_demo(con)} sesiones de ejemplo cargadas")
    con.close()


if __name__ == "__main__":
    main()
