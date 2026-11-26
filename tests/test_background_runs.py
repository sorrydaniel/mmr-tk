"""The conversion must actually run in the background.

It did not. `spawn` asked asyncio for a running loop, but the route that calls it is a
sync `def`, so FastAPI runs it in a worker thread where there is no loop - and the
fallback ran the whole conversion inline. On the deployment the POST blocked for 1.8 s
with the mock converter; with a real model and an 80-row TK it would block for minutes
and be cut by the platform proxy, which is the single failure the design exists to
prevent.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import select

from app import runner
from app.models import Conversion, Run
from app.seed import SAMPLE_MMR_TEXT


@pytest.fixture
def background(monkeypatch):
    """Undo the suite-wide inline default for these tests only."""
    monkeypatch.setattr(runner, "INLINE", False)
    yield


def _queue(session) -> tuple[Conversion, Run]:
    conversion = Conversion(
        title="Taust", mmr_id="mmr_bg", mmr_text=SAMPLE_MMR_TEXT, procurement_profile="COTS"
    )
    session.add(conversion)
    session.flush()
    run = runner.queue_run(session, conversion)
    session.commit()
    return conversion, run


def test_spawn_returns_before_the_run_finishes(seeded, background):
    session = seeded
    _conversion, run = _queue(session)

    started = time.perf_counter()
    future = runner.spawn(run.id, mock_delay=1.0)
    handed_back_after = time.perf_counter() - started

    assert future is not None
    # The call must return promptly; the work takes at least the mock delay.
    assert handed_back_after < 0.5, f"spawn blocked for {handed_back_after:.2f}s"

    future.result(timeout=30)
    assert time.perf_counter() - started >= 1.0


def test_the_backgrounded_run_actually_completes(seeded, background):
    session = seeded
    conversion, run = _queue(session)

    runner.spawn(run.id, mock_delay=0.0).result(timeout=30)
    session.expire_all()

    finished = session.get(Run, run.id)
    assert finished.status == "done"
    assert finished.rows_generated > 0
    rows = session.scalars(
        select(Conversion).where(Conversion.id == conversion.id)
    ).one().requirements
    assert len(rows) == finished.rows_generated


def test_inline_mode_still_runs_to_completion(seeded):
    """The suite relies on this, so it is worth asserting rather than assuming."""
    session = seeded
    _conversion, run = _queue(session)

    assert runner.spawn(run.id, mock_delay=0.0) is None
    session.expire_all()
    assert session.get(Run, run.id).status == "done"
