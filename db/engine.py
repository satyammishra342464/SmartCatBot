"""Engine, pooled session factory, and schema creation."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base
from service.config import get_settings

_engine = None
_SessionLocal: sessionmaker | None = None


def _init() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        return
    settings = get_settings()
    url = settings.database_url
    # Fail fast if Postgres isn't reachable instead of hanging on a long OS-level
    # TCP timeout (the "stuck on _bootstrap()" symptom on Windows).
    connect_args: dict = {}
    if url.startswith("postgresql"):
        connect_args["connect_timeout"] = 3
    # pool_pre_ping avoids stale-connection errors; the pool gives real
    # concurrency (the whole point of moving off single-writer SQLite).
    engine_kwargs: dict = {"pool_pre_ping": True, "future": True, "connect_args": connect_args}
    if not url.startswith("sqlite"):
        engine_kwargs.update(pool_size=10, max_overflow=20)
    _engine = create_engine(url, **engine_kwargs)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, class_=Session)


def get_engine():
    _init()
    return _engine


def init_db() -> None:
    """Create all tables (idempotent). POC-level migration; Alembic is future work."""
    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, rollback on error, always close."""
    _init()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
