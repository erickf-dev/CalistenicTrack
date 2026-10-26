"""Conexión a SQLite. Una conexión por petición, con claves foráneas activas."""
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "calistenia.db"


def db_path() -> Path:
    return Path(os.environ.get("CALISTENIA_DB", DEFAULT_DB))


def get_conn():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
