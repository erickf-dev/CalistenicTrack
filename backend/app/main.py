"""API del Tracker de Calistenia: registro de una sesión (paso 2)."""
import sqlite3
from datetime import date

from fastapi import Depends, FastAPI, HTTPException

from .database import get_conn
from .schemas import NoteIn, SetCreate, SetUpdate, WorkoutCreate, WorkoutFinish

app = FastAPI(title="Calistenia Tracker")


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def get_workout_or_404(con: sqlite3.Connection, workout_id: int) -> sqlite3.Row:
    w = con.execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
    if w is None:
        raise HTTPException(404, "Sesión no encontrada")
    return w


def require_open(w: sqlite3.Row) -> None:
    if w["finished"]:
        raise HTTPException(409, "La sesión ya está cerrada")


# ---------- Catálogo ----------

@app.get("/exercises")
def list_exercises(con=Depends(get_conn)):
    return rows(con.execute("SELECT * FROM exercises WHERE archived = 0 ORDER BY category, name"))


@app.get("/routines")
def list_routines(con=Depends(get_conn)):
    return rows(con.execute("SELECT * FROM routines WHERE archived = 0 ORDER BY suggested_day, name"))


@app.get("/routines/{routine_id}")
def get_routine(routine_id: int, con=Depends(get_conn)):
    r = con.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Rutina no encontrada")
    items = rows(con.execute(
        """SELECT re.position, re.target_sets, re.target_reps_min, re.target_reps_max,
                  re.target_seconds, re.rest_seconds, e.id AS exercise_id, e.name,
                  e.category, e.measure_type, e.per_side
           FROM routine_exercises re JOIN exercises e ON e.id = re.exercise_id
           WHERE re.routine_id = ? ORDER BY re.position""", (routine_id,)))
    return {**dict(r), "exercises": items}


# ---------- Sesiones ----------

@app.post("/workouts", status_code=201)
def start_workout(body: WorkoutCreate, con=Depends(get_conn)):
    bw = body.bodyweight_kg
    if bw is None:  # último peso corporal conocido
        row = con.execute("SELECT bodyweight_kg FROM body_metrics ORDER BY date DESC LIMIT 1").fetchone()
        if row is None:
            row = con.execute(
                "SELECT bodyweight_kg FROM workouts WHERE bodyweight_kg IS NOT NULL ORDER BY date DESC, id DESC LIMIT 1"
            ).fetchone()
        bw = row[0] if row else None
    try:
        cur = con.execute(
            "INSERT INTO workouts (date, routine_id, bodyweight_kg) VALUES (?,?,?)",
            ((body.date or date.today()).isoformat(), body.routine_id, bw),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(422, "Rutina inexistente")
    return get_workout(cur.lastrowid, con)


@app.get("/workouts/{workout_id}")
def get_workout(workout_id: int, con=Depends(get_conn)):
    w = get_workout_or_404(con, workout_id)
    sets = rows(con.execute(
        "SELECT * FROM sets WHERE workout_id = ? ORDER BY exercise_id, set_number", (workout_id,)))
    notes = rows(con.execute(
        "SELECT exercise_id, note FROM workout_exercise_notes WHERE workout_id = ?", (workout_id,)))
    return {**dict(w), "sets": sets, "notes": notes}


@app.patch("/workouts/{workout_id}/finish")
def finish_workout(workout_id: int, body: WorkoutFinish, con=Depends(get_conn)):
    w = get_workout_or_404(con, workout_id)
    require_open(w)
    con.execute(
        "UPDATE workouts SET finished = 1, duration_seconds = ?, feeling = ?, notes = ? WHERE id = ?",
        (body.duration_seconds, body.feeling, body.notes, workout_id))
    return summary(workout_id, con)


@app.get("/workouts/{workout_id}/summary")
def summary(workout_id: int, con=Depends(get_conn)):
    w = get_workout_or_404(con, workout_id)
    s = con.execute(
        """SELECT COUNT(*) AS total_sets,
                  COALESCE(SUM(reps), 0) AS total_reps,
                  COALESCE(SUM(seconds), 0) AS total_seconds
           FROM sets WHERE workout_id = ? AND is_warmup = 0""", (workout_id,)).fetchone()
    return {"workout_id": workout_id, "finished": bool(w["finished"]),
            "duration_seconds": w["duration_seconds"], **dict(s)}


@app.put("/workouts/{workout_id}/notes/{exercise_id}")
def set_note(workout_id: int, exercise_id: int, body: NoteIn, con=Depends(get_conn)):
    get_workout_or_404(con, workout_id)
    try:
        con.execute(
            """INSERT INTO workout_exercise_notes (workout_id, exercise_id, note) VALUES (?,?,?)
               ON CONFLICT(workout_id, exercise_id) DO UPDATE SET note = excluded.note""",
            (workout_id, exercise_id, body.note))
    except sqlite3.IntegrityError:
        raise HTTPException(422, "Ejercicio inexistente")
    return {"exercise_id": exercise_id, "note": body.note}


# ---------- Series ----------

@app.post("/workouts/{workout_id}/sets", status_code=201)
def add_set(workout_id: int, body: SetCreate, con=Depends(get_conn)):
    require_open(get_workout_or_404(con, workout_id))
    n = con.execute(
        "SELECT COALESCE(MAX(set_number), 0) + 1 FROM sets WHERE workout_id = ? AND exercise_id = ?",
        (workout_id, body.exercise_id)).fetchone()[0]
    try:
        cur = con.execute(
            """INSERT INTO sets (workout_id, exercise_id, set_number, reps, seconds, side,
                                 extra_weight_kg, rpe, is_warmup) VALUES (?,?,?,?,?,?,?,?,?)""",
            (workout_id, body.exercise_id, n, body.reps, body.seconds, body.side,
             body.extra_weight_kg, body.rpe, int(body.is_warmup)))
    except sqlite3.IntegrityError:
        raise HTTPException(422, "Ejercicio inexistente")
    return dict(con.execute("SELECT * FROM sets WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.patch("/sets/{set_id}")
def update_set(set_id: int, body: SetUpdate, con=Depends(get_conn)):
    s = con.execute("SELECT * FROM sets WHERE id = ?", (set_id,)).fetchone()
    if s is None:
        raise HTTPException(404, "Serie no encontrada")
    changes = body.model_dump(exclude_unset=True)
    if "is_warmup" in changes:
        changes["is_warmup"] = int(changes["is_warmup"])
    merged = {**dict(s), **changes}
    if merged["reps"] is None and merged["seconds"] is None:
        raise HTTPException(422, "Una serie necesita reps o segundos")
    if changes:
        cols = ", ".join(f"{k} = ?" for k in changes)
        con.execute(f"UPDATE sets SET {cols} WHERE id = ?", (*changes.values(), set_id))
    return dict(con.execute("SELECT * FROM sets WHERE id = ?", (set_id,)).fetchone())


@app.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: int, con=Depends(get_conn)):
    cur = con.execute("DELETE FROM sets WHERE id = ?", (set_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Serie no encontrada")


# ---------- Referencia "Última vez" ----------

@app.get("/exercises/{exercise_id}/last")
def last_time(exercise_id: int, before_workout_id: int | None = None, con=Depends(get_conn)):
    """Series de la sesión anterior con este ejercicio (sin calentamiento)."""
    params: list = [exercise_id]
    extra = ""
    if before_workout_id is not None:
        extra = "AND w.id <> ?"
        params.append(before_workout_id)
    w = con.execute(
        f"""SELECT w.id, w.date FROM workouts w
            WHERE EXISTS (SELECT 1 FROM sets s WHERE s.workout_id = w.id
                          AND s.exercise_id = ? AND s.is_warmup = 0) {extra}
            ORDER BY w.date DESC, w.id DESC LIMIT 1""", params).fetchone()
    if w is None:
        return {"workout_id": None, "date": None, "sets": []}
    sets = rows(con.execute(
        """SELECT set_number, reps, seconds, side, extra_weight_kg FROM sets
           WHERE workout_id = ? AND exercise_id = ? AND is_warmup = 0 ORDER BY set_number""",
        (w["id"], exercise_id)))
    return {"workout_id": w["id"], "date": w["date"], "sets": sets}
