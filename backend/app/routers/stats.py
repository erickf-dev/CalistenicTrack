"""Estadísticas básicas: volumen semanal y récords personales (paso 4)."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from ..database import get_conn, rows

router = APIRouter(prefix="/stats", tags=["estadísticas"])


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


@router.get("/volume/weekly")
def weekly_volume(weeks: int = Query(8, ge=1, le=52), con=Depends(get_conn)):
    """Volumen por semana y categoría, con el cambio % contra la semana anterior.

    Se agrupa por el lunes de cada semana (no por strftime('%W')) para que una
    semana que cruza el 31 de diciembre no se parta en dos.
    Volumen = reps totales, segundos totales y carga extra (reps × kg extra).
    El calentamiento no cuenta.
    """
    first = monday_of(date.today()) - timedelta(weeks=weeks - 1)
    data = rows(con.execute(
        """WITH weekly AS (
               SELECT date(w.date, 'weekday 0', '-6 days') AS week_start,
                      e.category,
                      COUNT(*)                                   AS sets,
                      COALESCE(SUM(s.reps), 0)                   AS reps,
                      COALESCE(SUM(s.seconds), 0)                AS seconds,
                      COALESCE(SUM(s.reps * s.extra_weight_kg), 0) AS load_kg
               FROM sets s
               JOIN workouts w  ON w.id = s.workout_id
               JOIN exercises e ON e.id = s.exercise_id
               WHERE s.is_warmup = 0 AND w.date >= date(?, '-7 days')
               GROUP BY week_start, e.category),
           compared AS (
               SELECT *,
                      LAG(week_start) OVER (PARTITION BY category ORDER BY week_start) AS lag_week,
                      LAG(reps)       OVER (PARTITION BY category ORDER BY week_start) AS lag_reps,
                      LAG(seconds)    OVER (PARTITION BY category ORDER BY week_start) AS lag_seconds
               FROM weekly)
           SELECT week_start, category, sets, reps, seconds, load_kg,
                  CASE WHEN lag_week = date(week_start, '-7 days') THEN lag_reps    END AS prev_reps,
                  CASE WHEN lag_week = date(week_start, '-7 days') THEN lag_seconds END AS prev_seconds,
                  CASE WHEN lag_week = date(week_start, '-7 days') AND lag_reps > 0
                       THEN ROUND(100.0 * (reps - lag_reps) / lag_reps, 1) END       AS pct_change_reps,
                  CASE WHEN lag_week = date(week_start, '-7 days') AND lag_seconds > 0
                       THEN ROUND(100.0 * (seconds - lag_seconds) / lag_seconds, 1) END AS pct_change_seconds
           FROM compared
           WHERE week_start >= ?
           ORDER BY week_start, category""", (first.isoformat(), first.isoformat())))
    return data


@router.get("/records")
def personal_records(con=Depends(get_conn)):
    """Mejor serie por ejercicio (reps o segundos) y la serie con más carga extra.

    Ante un empate gana la más antigua: el récord se logró primero ese día.
    """
    data = rows(con.execute(
        """WITH base AS (
               SELECT s.exercise_id, s.reps, s.seconds, s.extra_weight_kg, w.date,
                      CASE e.measure_type WHEN 'tiempo' THEN s.seconds ELSE s.reps END AS metric
               FROM sets s
               JOIN workouts w  ON w.id = s.workout_id
               JOIN exercises e ON e.id = s.exercise_id
               WHERE s.is_warmup = 0),
           best AS (
               SELECT *, ROW_NUMBER() OVER (
                          PARTITION BY exercise_id
                          ORDER BY metric DESC, extra_weight_kg DESC, date ASC) AS rn
               FROM base WHERE metric IS NOT NULL),
           heavy AS (
               SELECT *, ROW_NUMBER() OVER (
                          PARTITION BY exercise_id
                          ORDER BY extra_weight_kg DESC, metric DESC, date ASC) AS rn
               FROM base WHERE extra_weight_kg > 0 AND metric IS NOT NULL)
           SELECT e.id AS exercise_id, e.name, e.category, e.measure_type,
                  b.metric AS best_value, b.extra_weight_kg AS best_extra_kg, b.date AS best_date,
                  h.metric AS heavy_value, h.extra_weight_kg AS heavy_extra_kg, h.date AS heavy_date
           FROM exercises e
           JOIN best b ON b.exercise_id = e.id AND b.rn = 1
           LEFT JOIN heavy h ON h.exercise_id = e.id AND h.rn = 1
           ORDER BY e.category, e.name"""))
    return [
        {
            "exercise_id": r["exercise_id"], "name": r["name"], "category": r["category"],
            "measure_type": r["measure_type"],
            "best": {"value": r["best_value"], "extra_weight_kg": r["best_extra_kg"], "date": r["best_date"]},
            "heaviest": None if r["heavy_extra_kg"] is None else
                {"value": r["heavy_value"], "extra_weight_kg": r["heavy_extra_kg"], "date": r["heavy_date"]},
        }
        for r in data
    ]
