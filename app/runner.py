"""Running a conversion in the background.

A ~80-row TK is minutes of generation. A blocking HTTP request would be cut by the
platform proxy long before the model finished, so the request only queues the work and the
page polls for progress. The trade-off is that a restart kills in-flight work, which is why
orphaned runs are failed on startup instead of sitting at "calling" forever.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app import settings_store
from app.config import MAX_SEGMENTS, get_config
from app.converter import anthropic_client, mock
from app.converter.base import ConversionFailed, ConverterResult
from app.db import session_scope
from app.models import (
    RUN_ACTIVE_STATUSES,
    Conversion,
    Requirement,
    RequirementSnapshot,
    Run,
    Segment,
)
from app.pipeline import build_requirements, heading_lookup
from app.segmentation import Seg, numbered_text, segment_text

logger = logging.getLogger(__name__)

# Two workers: one conversion at a time is the realistic load, one spare so a second
# click is not stuck behind it.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mmrtk-run")

# Tests set this so a run completes before the assertion that follows it.
INLINE = False

ORPHAN_ERROR = (
    "Käivitus katkes serveri taaskäivitusel. Vajuta \"Proovi uuesti\", et uuesti alustada."
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- status -------------------------------------------------------------------------------


def _set_status(session: Session, run_id: int, status: str) -> None:
    session.execute(update(Run).where(Run.id == run_id).values(status=status))
    session.commit()


def recover_orphaned_runs(session: Session) -> int:
    """Anything still marked active at boot died with the previous process."""
    runs = list(session.scalars(select(Run).where(Run.status.in_(RUN_ACTIVE_STATUSES))))
    for run in runs:
        run.status = "failed"
        run.error = ORPHAN_ERROR
        run.finished_at = utcnow()
        if run.conversion is not None and run.conversion.status == "draft":
            run.conversion.status = "failed"
    if runs:
        session.commit()
        logger.warning("Marked %d orphaned run(s) as failed", len(runs))
    return len(runs)


# --- segmentation -------------------------------------------------------------------------


def store_segments(session: Session, conversion: Conversion, segments: list[Seg]) -> None:
    session.execute(delete(Segment).where(Segment.conversion_id == conversion.id))
    for seg in segments:
        session.add(
            Segment(
                conversion_id=conversion.id,
                sid=seg.sid,
                text=seg.text,
                segment_type=seg.segment_type,
                list_level=seg.list_level,
                order=seg.order,
            )
        )
    session.flush()


def load_segments(session: Session, conversion_id: int) -> list[Seg]:
    rows = session.scalars(
        select(Segment).where(Segment.conversion_id == conversion_id).order_by(Segment.order)
    )
    return [
        Seg(
            sid=row.sid,
            text=row.text,
            segment_type=row.segment_type,
            order=row.order,
            list_level=row.list_level,
        )
        for row in rows
    ]


def clear_draft(session: Session, conversion_id: int) -> None:
    """A re-run replaces the draft. Run rows stay in the log; the requirements do not."""
    session.execute(
        delete(RequirementSnapshot).where(RequirementSnapshot.conversion_id == conversion_id)
    )
    session.execute(delete(Requirement).where(Requirement.conversion_id == conversion_id))
    session.flush()


# --- the run -------------------------------------------------------------------------------


def queue_run(session: Session, conversion: Conversion) -> Run:
    run = Run(
        conversion_id=conversion.id,
        mmr_id=conversion.mmr_id,
        model="mock" if get_config().mock_mode else settings_store.get(session, settings_store.MODEL),
        mock=get_config().mock_mode,
        status="queued",
    )
    session.add(run)
    conversion.status = "draft"
    if conversion.first_llm_run_at is None:
        conversion.first_llm_run_at = utcnow()
    session.flush()
    return run


def _run_body(run_id: int, mock_delay: float | None, queued_at: float) -> None:
    """Body of a run. Owns its own session, because it outlives the request."""
    session = session_scope()
    try:
        run = session.get(Run, run_id)
        if run is None:
            return
        conversion = session.get(Conversion, run.conversion_id) if run.conversion_id else None
        if conversion is None:
            run.status = "failed"
            run.error = "Konversiooni ei leitud."
            run.finished_at = utcnow()
            session.commit()
            return

        run.queue_seconds = round(max(0.0, time.perf_counter() - queued_at), 3)

        # 1. splitting
        run.status = "splitting"
        session.commit()
        # Reuse the segmentation stored when the conversion was created. For an upload
        # that is the only place the document's own structure survives.
        segments = load_segments(session, conversion.id)
        if not segments:
            segments = segment_text(conversion.mmr_text or "")
            store_segments(session, conversion, segments)
        if not segments:
            raise ConversionFailed("MMR tekst on tühi - ei ole midagi teisendada.")
        if len(segments) > MAX_SEGMENTS:
            raise ConversionFailed(
                f"MMR on liiga pikk: {len(segments)} lõiku, lubatud kuni {MAX_SEGMENTS}. "
                "Jaga dokument väiksemateks osadeks."
            )
        session.commit()

        # 2. calling the model
        run.status = "calling"
        session.commit()
        valid_sids = {seg.sid for seg in segments}

        if get_config().mock_mode:
            result: ConverterResult = mock.convert(
                segments,
                heading_lookup=heading_lookup(segments),
                delay=mock.MOCK_DELAY_SECONDS if mock_delay is None else mock_delay,
            )
        else:
            result = anthropic_client.convert(
                api_key=get_config().anthropic_api_key or "",
                model=settings_store.get(session, settings_store.MODEL),
                system_prompt=settings_store.get(session, settings_store.SYSTEM_PROMPT),
                numbered_mmr=numbered_text(segments),
                temperature=settings_store.temperature(session),
                valid_sids=valid_sids,
            )

        # 3. validating and storing
        run.status = "validating"
        run.model = result.model
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.processing_seconds = result.processing_seconds
        run.retry_used = result.retry_used
        run.mock = result.mock
        session.commit()

        clear_draft(session, conversion.id)
        requirements = build_requirements(
            session, conversion, segments, result.rows, run_id=run.id
        )

        run.rows_generated = len(requirements)
        run.uncertain_rows = sum(1 for r in requirements if r.uncertain)
        run.schema_valid = True
        run.status = "done"
        run.finished_at = utcnow()
        conversion.status = "converted"
        session.commit()

    except ConversionFailed as failure:
        session.rollback()
        _fail(session, run_id, failure.message, retry_used=failure.retry_used)
    except Exception as exc:  # noqa: BLE001 - the run log is the place this is reported
        logger.exception("Run %s failed", run_id)
        session.rollback()
        _fail(session, run_id, f"Ootamatu viga: {type(exc).__name__}: {exc}")
    finally:
        session.close()


def _fail(session: Session, run_id: int, message: str, *, retry_used: bool = False) -> None:
    run = session.get(Run, run_id)
    if run is None:
        return
    run.status = "failed"
    run.error = message[:4000]
    run.schema_valid = False
    run.retry_used = retry_used or run.retry_used
    run.finished_at = utcnow()
    if run.conversion is not None:
        run.conversion.status = "failed"
    session.commit()


def run_sync(run_id: int, *, mock_delay: float | None = None) -> None:
    """Run inline, start to finish. Used by tests."""
    _run_body(run_id, mock_delay, time.perf_counter())


def spawn(run_id: int, *, mock_delay: float | None = None):
    """Start the run and return immediately.

    This used to hand the work to asyncio, which quietly did nothing: the route that
    calls it is a sync `def`, so FastAPI runs it in a worker thread where there is no
    running event loop, and the fallback executed the whole run inline. The POST then
    blocked for the length of the conversion - 1.8 s with the mock, minutes with a real
    model, which is exactly the proxy timeout the background design exists to avoid.

    A thread pool has no such dependency on the calling context.
    """
    queued_at = time.perf_counter()
    if INLINE:
        _run_body(run_id, mock_delay, queued_at)
        return None
    return _executor.submit(_run_body, run_id, mock_delay, queued_at)


def shutdown() -> None:
    """Stop accepting work at shutdown; anything in flight is recovered on next boot."""
    _executor.shutdown(wait=False, cancel_futures=True)
