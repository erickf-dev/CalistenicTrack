-- Tracker de Calistenia y Progresión · esquema SQLite
-- Activar en CADA conexión: PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS exercises (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    category      TEXT    NOT NULL CHECK (category IN ('empuje','traccion','piernas','core')),
    measure_type  TEXT    NOT NULL DEFAULT 'reps' CHECK (measure_type IN ('reps','tiempo')),
    per_side      INTEGER NOT NULL DEFAULT 0 CHECK (per_side IN (0,1)),   -- 1 = se registra por lado (búlgaras)
    load_unit     TEXT    NOT NULL DEFAULT 'kg',
    archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
);

CREATE TABLE IF NOT EXISTS routines (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    suggested_day INTEGER CHECK (suggested_day BETWEEN 0 AND 6),          -- 0 = lunes ... 6 = domingo
    notes         TEXT,
    archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
);

CREATE TABLE IF NOT EXISTS routine_exercises (
    routine_id       INTEGER NOT NULL REFERENCES routines(id)  ON DELETE CASCADE,
    exercise_id      INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    position         INTEGER NOT NULL,
    target_sets      INTEGER NOT NULL DEFAULT 3 CHECK (target_sets > 0),
    target_reps_min  INTEGER,   -- rango para la doble progresión (ej. 6 a 10)
    target_reps_max  INTEGER,
    target_seconds   INTEGER,   -- para ejercicios por tiempo
    rest_seconds     INTEGER NOT NULL DEFAULT 90,
    PRIMARY KEY (routine_id, exercise_id),
    CHECK (target_reps_min IS NULL OR target_reps_max IS NULL OR target_reps_min <= target_reps_max)
);

CREATE TABLE IF NOT EXISTS workouts (
    id               INTEGER PRIMARY KEY,
    date             TEXT    NOT NULL,                       -- 'YYYY-MM-DD'
    routine_id       INTEGER REFERENCES routines(id) ON DELETE SET NULL,
    bodyweight_kg    REAL,                                   -- peso corporal vigente en la sesión
    duration_seconds INTEGER,
    feeling          INTEGER CHECK (feeling BETWEEN 1 AND 5),
    notes            TEXT,
    finished         INTEGER NOT NULL DEFAULT 0 CHECK (finished IN (0,1))
);

CREATE TABLE IF NOT EXISTS sets (
    id              INTEGER PRIMARY KEY,
    workout_id      INTEGER NOT NULL REFERENCES workouts(id)  ON DELETE CASCADE,
    exercise_id     INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    set_number      INTEGER NOT NULL CHECK (set_number > 0),
    reps            INTEGER CHECK (reps BETWEEN 0 AND 200),
    seconds         INTEGER CHECK (seconds >= 0),
    side            TEXT    NOT NULL DEFAULT 'ambos' CHECK (side IN ('izq','der','ambos')),
    extra_weight_kg REAL    NOT NULL DEFAULT 0 CHECK (extra_weight_kg >= 0),
    rpe             REAL    CHECK (rpe BETWEEN 1 AND 10),
    is_warmup       INTEGER NOT NULL DEFAULT 0 CHECK (is_warmup IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (reps IS NOT NULL OR seconds IS NOT NULL)          -- no se permiten series vacías
);

CREATE TABLE IF NOT EXISTS workout_exercise_notes (          -- nota por ejercicio dentro de una sesión
    workout_id  INTEGER NOT NULL REFERENCES workouts(id)  ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    note        TEXT    NOT NULL,
    PRIMARY KEY (workout_id, exercise_id)
);

CREATE TABLE IF NOT EXISTS body_metrics (
    id            INTEGER PRIMARY KEY,
    date          TEXT NOT NULL UNIQUE,
    bodyweight_kg REAL NOT NULL CHECK (bodyweight_kg > 0)
);

CREATE INDEX IF NOT EXISTS idx_workouts_date      ON workouts(date);
CREATE INDEX IF NOT EXISTS idx_sets_exercise      ON sets(exercise_id, workout_id);
CREATE INDEX IF NOT EXISTS idx_sets_workout       ON sets(workout_id);
