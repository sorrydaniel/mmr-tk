"""The run log: the research record of every conversion attempt."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Conversion, Run
from app.web import render

router = APIRouter()

CSV_COLUMNS = (
    "run_id",
    "conversion_id",
    "mmr_id",
    "created_at",
    "finished_at",
    "model",
    "input_tokens",
    "output_tokens",
    "processing_seconds",
    "queue_seconds",
    "rows_generated",
    "schema_valid",
    "uncertain_rows",
    "retry_used",
    "mock",
    "status",
    "error",
)


def _runs(session: Session) -> list[Run]:
    return list(session.scalars(select(Run).order_by(desc(Run.created_at))))


@router.get("/logi")
def run_log(request: Request, session: Session = Depends(get_db)):
    return render(
        request,
        "runs.html",
        {
            "conversions": list(
                session.scalars(select(Conversion).order_by(desc(Conversion.created_at)))
            ),
            "selected": None,
            "runs": _runs(session),
        },
    )


@router.get("/logi/csv")
def run_log_csv(session: Session = Depends(get_db)):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for run in _runs(session):
        writer.writerow(
            [
                run.id,
                run.conversion_id or "",
                run.mmr_id,
                run.created_at.isoformat() if run.created_at else "",
                run.finished_at.isoformat() if run.finished_at else "",
                run.model,
                run.input_tokens,
                run.output_tokens,
                f"{run.processing_seconds:.3f}",
                f"{run.queue_seconds:.3f}",
                run.rows_generated,
                "jah" if run.schema_valid else "ei",
                run.uncertain_rows,
                "jah" if run.retry_used else "ei",
                "jah" if run.mock else "ei",
                run.status,
                (run.error or "").replace("\n", " "),
            ]
        )
    # BOM so Excel opens the semicolon-separated file in the right encoding.
    payload = "﻿" + buffer.getvalue()
    return StreamingResponse(
        io.BytesIO(payload.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kaivituste_logi.csv"'},
    )
