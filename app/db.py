"""Engine and session handling.

The engine is created lazily so that an unreachable or unset DATABASE_URL surfaces as a
friendly error page rather than a crash at import time.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_config


class DatabaseUnavailable(RuntimeError):
    """Raised when the database cannot be reached or is not configured."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        return {"future": True}
    return {
        "future": True,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_recycle": 1800,
    }


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        if not get_config().database_url:
            raise DatabaseUnavailable("DATABASE_URL puudub")
        url = get_config().database_url
        _engine = create_engine(url, **_engine_kwargs(url))
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def set_engine(engine: Engine) -> None:
    """Used by tests to bind an in-memory SQLite engine."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def reset_engine() -> None:
    global _engine, _session_factory
    _engine = None
    _session_factory = None


def session_scope() -> Session:
    return get_session_factory()()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    session = session_scope()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
