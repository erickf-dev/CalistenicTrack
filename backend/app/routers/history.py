"""Historial de sesiones y evolución por ejercicio (paso 3)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_conn, rows

router = APIRouter(tags=["historial"])


@router.get("/workouts")
def list_workouts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    routine_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    con=Depends(get_conn),
):
    """Sesiones de la más reciente a la más antigua, con totales (sin calentamiento)."""
    where, params = [], []
    if routine_id is not None:
        where.append("w.routine_id = ?"); params.append(routine_id)
    if date_from:
        where.append("w.date >= ?"); params.append(date_from.isoformat())
    if date_to:
        where.append("w.date <= ?"); params.append(date_to.isoformat())
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = con.execute(f"SELECT COUNT(*) FROM workouts w {clause}", params).fetchone()[0]
    items = rows(con.execute(
        f"""SELECT w.id, w.date, w.routine_id, r.name AS routine_name, w.bodyweight_kg,
                   w.duration_seconds, w.feeling, w.finished,
                   COALESCE(SUM(CASE WHEN s.is_warmup = 0 THEN 1 END), 0)          AS total_sets,
                   COALESCE(SUM(CASE WHEN s.is_warmup = 0 THEN s.reps END), 0)     AS total_reps,
                   COALESCE(SUM(CASE WHEN s.is_warmup = 0 THEN s.seconds END), 0)  AS total_seconds
            FROM workouts w
            LEFT JOIN routines r ON r.id = w.routine_id
            LEFT JOIN sets s     ON s.workout_id = w.id
            {clause}
            GROUP BY w.id
            ORDER BY w.date DESC, w.id DESC
            LIMIT ? OFFSET ?""", (*params, limit, offset)))
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.delete("/workouts/{workout_id}", status_code=204)
def delete_workout(workout_id: int, con=Depends(get_conn)):
    """Borra la sesión; sus series y notas se eliminan en cascada."""
    cur = con.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Sesión no encontrada")


@router.get("/exercises/{exercise_id}/history")
def exercise_history(exercise_id: int, limit: int = Query(50, ge=1, le=500), con=Depends(get_conn)):
    """Una fila por sesión (orden cronológico), lista para graficar."""
    if con.execute("SELECT 1 FROM exercises WHERE id = ?", (exercise_id,)).fetchone() is None:
        raise HTTPException(404, "Ejercicio no encontrado")
    data = rows(con.execute(
        """WITH per_workout AS (
               SELECT w.id AS workout_id, w.date, w.bodyweight_kg,
                      COUNT(*)               AS sets,
                      SUM(s.reps)            AS total_reps,
                      MAX(s.reps)            AS best_reps,
                      SUM(s.seconds)         AS total_seconds,
                      MAX(s.seconds)         AS best_seconds,
                      MAX(s.extra_weight_kg) AS max_extra_kg
               FROM sets s JOIN workouts w ON w.id = s.workout_id
               WHERE s.exercise_id = ? AND s.is_warmup = 0
               GROUP BY w.id)
           SELECT *,
                  LAG(best_reps)     OVER (ORDER BY date, workout_id) AS prev_best_reps,
                  LAG(total_reps)    OVER (ORDER BY date, workout_id) AS prev_total_reps,
                  LAG(best_seconds)  OVER (ORDER BY date, workout_id) AS prev_best_seconds
           FROM per_workout ORDER BY date, workout_id""", (exercise_id,)))
    return data[-limit:]
