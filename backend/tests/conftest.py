import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("CALISTENIA_DB", str(db))
    # reutiliza el script real de semillas apuntando a la BD temporal
    code = (
        "import sys; sys.path.insert(0, 'db'); import init_db; "
        f"from pathlib import Path; init_db.DB_PATH = Path(r'{db}'); init_db.main()"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, capture_output=True)
    from backend.app.main import app
    return TestClient(app)
