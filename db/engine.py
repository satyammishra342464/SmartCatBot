"""Engine, pooled session factory, and schema creation."""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base
from service.config import get_settings

_engine = None
_SessionLocal: sessionmaker | None = None
_active_url: str = ""  # the URL actually in use (may differ from config after fallback)


def _make_engine(url: str):
    connect_args: dict = {}
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("postgresql"):
        connect_args["connect_timeout"] = 3
        kwargs.update(connect_args=connect_args, pool_size=10, max_overflow=20)
    else:
        kwargs["connect_args"] = connect_args
    return create_engine(url, **kwargs)


def _sqlite_fallback_url() -> str:
    # /tmp persists for the lifetime of a Streamlit Cloud container; fine for demo.
    path = os.path.join(tempfile.gettempdir(), "smartcat_fallback.db")
    return "sqlite:///" + path.replace("\\", "/")


def _init() -> None:
    global _engine, _SessionLocal, _active_url
    if _engine is not None:
        return
    url = get_settings().database_url
    if url.startswith("postgresql"):
        try:
            eng = _make_engine(url)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            _engine = eng
            _active_url = url
        except Exception:
            # Postgres unreachable (e.g. Streamlit Cloud) — fall back to SQLite.
            fallback = _sqlite_fallback_url()
            _engine = _make_engine(fallback)
            _active_url = fallback
    else:
        _engine = _make_engine(url)
        _active_url = url
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, class_=Session)


def get_engine():
    _init()
    return _engine


def active_db_url() -> str:
    """Return the URL the engine is actually connected to (may be SQLite fallback)."""
    _init()
    return _active_url


def init_db() -> None:
    """Create all tables (idempotent)."""
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
