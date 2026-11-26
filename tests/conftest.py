"""Test setup.

Every test runs against SQLite in memory with the mock converter: no real database, no
API key, no network. That is a requirement, not a convenience -- the deployment database
holds study data and the API key costs money.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import db as db_module
from app.config import reload_config
from app.models import Base


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    reload_config()
    yield
    reload_config()


@pytest.fixture(autouse=True)
def fast_mock(monkeypatch):
    """The 1.5 s mock delay exists for the UI, not for the test suite."""
    from app.converter import mock

    monkeypatch.setattr(mock, "MOCK_DELAY_SECONDS", 0.0)
    yield


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    db_module.set_engine(eng)
    yield eng
    db_module.reset_engine()
    eng.dispose()


@pytest.fixture
def session(engine):
    sess = db_module.session_scope()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def seeded(session):
    from app.seed import seed_all

    seed_all(session)
    return session


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
