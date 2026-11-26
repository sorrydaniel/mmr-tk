"""The initial migration must match the models.

Phases 2 and 3 are supposed to ship as code only, which is only true if every table they
need already exists. This catches the drift that would otherwise show up against the
production database months from now.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.models import Base

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "migrations" / "versions" / "0001_initial.py"
)

EXPECTED_TABLES = {
    "answer_key",
    "blind_code",
    "conversion",
    "manual_import",
    "missing_note",
    "requirement",
    "requirement_flag",
    "requirement_snapshot",
    "review",
    "run",
    "segment",
    "setting",
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("initial_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_migration():
    engine = create_engine("sqlite://", poolclass=StaticPool, future=True)
    module = _load_migration()
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()
    return engine


def test_models_cover_all_three_phases():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_migration_has_a_single_head_with_no_predecessor():
    module = _load_migration()
    assert module.revision == "0001_initial"
    assert module.down_revision is None


def test_migration_creates_every_table():
    engine = _apply_migration()
    with engine.connect() as connection:
        names = set(inspect(connection).get_table_names())
    assert EXPECTED_TABLES <= names


def test_no_structural_drift_between_migration_and_models():
    engine = _apply_migration()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)

    structural = [
        entry
        for entry in diff
        if isinstance(entry, tuple)
        and entry[0] in ("add_table", "remove_table", "add_column", "remove_column")
    ]
    assert structural == [], structural
