"""Test setup: point the DB at a throwaway SQLite file (so tests need no
Postgres) and create the schema once per session. Env is set BEFORE
importing any db/service module so the engine binds to SQLite."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
os.environ["DATABASE_URL"] = "sqlite:///" + _db.name.replace(os.sep, "/")

from service.config import get_settings  # noqa: E402

get_settings.cache_clear()

import pytest  # noqa: E402

from db.engine import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db()
    yield
