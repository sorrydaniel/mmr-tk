from __future__ import annotations

import io
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import runner, settings_store
from app.config import MAX_SEGMENTS, MAX_UPLOAD_BYTES
from app.db import get_db
from app.excel import clean_export
from app.models import (
    CLASSIFICATIONS,
    PROCUREMENT_PROFILES,
    VERIF_METHODS,
    VERIF_STAGES,
    Conversion,
    Requirement,
    Run,
    Segment,
)
from app.pipeline import changed_fields
from app.segmentation import UnsupportedUpload, render_text, segment_text, segment_upload
from app.web import render

router = APIRouter()


def _sidebar(session: Session) -> list[Conversion]:
    return list(session.scalars(select(Conversion).order_by(desc(Conversion.created_at))))


def _get_conversion(session: Session, conversion_id: int) -> Conversion:
    conversion = session.get(Conversion, conversion_id)
    if conversion is None:
        raise HTTPException(status_code=404, detail="Konversiooni ei leitud")
    return conversion


def _active_requirements(session: Session, conversion_id: int) -> list[Requirement]:
    return list(
        session.scalars(
            select(Requirement)
            .where(Requirement.conversion_id == conversion_id, Requirement.deleted.is_(False))
            .order_by(Requirement.order)
        )
    )


def _segments(session: Session, conversion_id: int) -> list[Segment]:
    return list(
        session.scalars(
            select(Segment).where(Segment.conversion_id == conversion_id).order_by(Segment.order)
        )
    )


def _latest_run(session: Session, conversion_id: int) -> Run | None:
    return session.scalars(
        select(Run)
        .where(Run.conversion_id == conversion_id)
        .order_by(desc(Run.created_at))
        .limit(1)
    ).first()


def _ascii_filename(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in folded) or "tk"


@router.get("/")
def index(request: Request, session: Session = Depends(get_db)):
    conversions = _sidebar(session)
    return render(
        request,
        "index.html",
        {"conversions": conversions, "selected": None},
    )


@router.get("/uus")
def new_form(request: Request, session: Session = Depends(get_db)):
    return render(
        request,
        "new.html",
        {
            "conversions": _sidebar(session),
            "selected": None,
            "profiles": PROCUREMENT_PROFILES,
            "error": None,
        },
    )


@router.post("/uus")
async def create(
    request: Request,
    session: Session = Depends(get_db),
    title: str = Form(""),
    mmr_id: str = Form(""),
    procurement_profile: str = Form("COTS"),
    mmr_text: str = Form(""),
    upload: UploadFile | None = File(None),
):
    error: str | None = None
    text = (mmr_text or "").strip()
    segments = None

    if upload is not None and upload.filename:
        data = await upload.read()
        if len(data) > MAX_UPLOAD_BYTES:
            error = "Fail on suurem kui 5 MB."
        else:
            try:
                # Keep the parsed segments. Flattening to text and re-deriving the
                # structure later threw away everything Word actually told us -
                # heading styles, list membership, table rows - and merged bullets
                # into the sentence above them.
                segments = segment_upload(upload.filename, data)
                text = render_text(segments)
            except UnsupportedUpload as exc:
                error = str(exc)
            except Exception as exc:  # noqa: BLE001 - a corrupt upload must not 500
                error = f"Faili ei õnnestunud lugeda: {type(exc).__name__}"

    if not error:
        if not title.strip():
            error = "Pealkiri on kohustuslik."
        elif not mmr_id.strip():
            error = "MMR ID on kohustuslik."
        elif not text:
            error = "MMR tekst on tühi - kleebi tekst või lae fail üles."

    if error:
        return render(
            request,
            "new.html",
            {
                "conversions": _sidebar(session),
                "selected": None,
                "profiles": PROCUREMENT_PROFILES,
                "error": error,
                "form": {
                    "title": title,
                    "mmr_id": mmr_id,
                    "procurement_profile": procurement_profile,
                    "mmr_text": mmr_text,
                },
            },
            status_code=400,
        )

    profile = procurement_profile if procurement_profile in PROCUREMENT_PROFILES else "COTS"
    conversion = Conversion(
        title=title.strip(),
        mmr_id=mmr_id.strip(),
        mmr_text=text,
        procurement_profile=profile,
        status="draft",
    )
    session.add(conversion)
    session.flush()
    # Store the segmentation now, so an upload's structure is the authoritative split
    # and the run does not have to guess it back out of plain text.
    runner.store_segments(session, conversion, segments or segment_text(text))
    return RedirectResponse(f"/k/{conversion.id}", status_code=303)


@router.get("/k/{conversion_id}")
def show(request: Request, conversion_id: int, session: Session = Depends(get_db)):
    conversion = _get_conversion(session, conversion_id)
    requirements = _active_requirements(session, conversion_id)
    segments = _segments(session, conversion_id)
    if not segments:
        # Not yet converted: show the split the model would be given.
        segments = [
            Segment(
                conversion_id=conversion_id,
                sid=seg.sid,
                text=seg.text,
                segment_type=seg.segment_type,
                list_level=seg.list_level,
                order=seg.order,
            )
            for seg in segment_text(conversion.mmr_text or "")
        ]
    segment_text_by_sid = {seg.sid: seg.text for seg in segments}
    diffs = {req.id: changed_fields(req) for req in requirements}

    return render(
        request,
        "conversion.html",
        {
            "conversions": _sidebar(session),
            "selected": conversion,
            "conversion": conversion,
            "requirements": requirements,
            "segments": segments,
            "segment_text": segment_text_by_sid,
            "diffs": diffs,
            "run": _latest_run(session, conversion_id),
            "too_long": len(segments) > MAX_SEGMENTS,
            "max_segments": MAX_SEGMENTS,
            "methods": VERIF_METHODS,
            "stages": VERIF_STAGES,
            "classifications": CLASSIFICATIONS,
        },
    )


@router.post("/k/{conversion_id}/kustuta")
def delete(conversion_id: int, session: Session = Depends(get_db)):
    conversion = _get_conversion(session, conversion_id)
    session.delete(conversion)
    return RedirectResponse("/", status_code=303)


@router.post("/k/{conversion_id}/konverteeri")
def convert(request: Request, conversion_id: int, session: Session = Depends(get_db)):
    conversion = _get_conversion(session, conversion_id)
    run = runner.queue_run(session, conversion)
    session.commit()
    runner.spawn(run.id)
    return render(
        request,
        "partials/status.html",
        {"conversion": conversion, "run": run, "polling": True},
    )


@router.get("/k/{conversion_id}/staatus")
def status(request: Request, conversion_id: int, session: Session = Depends(get_db)):
    conversion = _get_conversion(session, conversion_id)
    run = _latest_run(session, conversion_id)
    if run is not None and run.status == "done":
        # Reload the page once, so the finished table and the export button appear.
        return Response(status_code=200, headers={"HX-Refresh": "true"})
    finished = run is None or run.status == "failed"
    return render(
        request,
        "partials/status.html",
        {"conversion": conversion, "run": run, "polling": not finished},
    )


@router.get("/k/{conversion_id}/eksport.xlsx")
def export_clean(conversion_id: int, session: Session = Depends(get_db)):
    conversion = _get_conversion(session, conversion_id)
    requirements = _active_requirements(session, conversion_id)
    rows = clean_export.rows_from_requirements(requirements)
    fills = {
        cls: settings_store.class_fill(session, cls) for cls in ("M", "N", "I", "OP")
    }
    group_label = settings_store.get(session, settings_store.GROUP_ROW_LABEL).strip()
    if not group_label and rows:
        group_label = rows[0].category
    payload = clean_export.to_bytes(
        rows, class_fills=fills, group_label=group_label or None
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    name = f"TK_{_ascii_filename(conversion.mmr_id)}_{stamp}.xlsx"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
