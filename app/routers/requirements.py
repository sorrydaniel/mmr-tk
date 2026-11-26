"""Inline editing of the draft (Paranda mode).

Every edit is saved immediately and marks the row `edited_by_user`, because the difference
between the immutable snapshot and the live row is the review-effort measurement. Deletes
are soft: a row the model invented is data, not noise, so it is kept and counted.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    CLASSIFICATIONS,
    VERIF_METHODS,
    VERIF_STAGES,
    Conversion,
    Requirement,
    Segment,
)
from app.pipeline import changed_fields
from app.web import render

router = APIRouter()

EDITABLE_FIELDS = {
    "category",
    "description",
    "classification",
    "verif_with_bid",
    "verif_method",
    "verif_stage",
    "verif_description",
    "comments",
}

ALLOWED_VALUES = {
    "classification": set(CLASSIFICATIONS),
    "verif_method": set(VERIF_METHODS),
    "verif_stage": set(VERIF_STAGES),
}


def _get_requirement(session: Session, requirement_id: int) -> Requirement:
    requirement = session.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Rida ei leitud")
    return requirement


def _segment_text(session: Session, conversion_id: int) -> dict[str, str]:
    rows = session.scalars(select(Segment).where(Segment.conversion_id == conversion_id))
    return {row.sid: row.text for row in rows}


def _row_response(request: Request, session: Session, requirement: Requirement):
    return render(
        request,
        "partials/row.html",
        {
            "r": requirement,
            "conversion": requirement.conversion,
            "segment_text": _segment_text(session, requirement.conversion_id),
            "diff": changed_fields(requirement),
            "methods": VERIF_METHODS,
            "stages": VERIF_STAGES,
            "classifications": CLASSIFICATIONS,
        },
    )


def _table_response(request: Request, session: Session, conversion: Conversion):
    requirements = list(
        session.scalars(
            select(Requirement)
            .where(Requirement.conversion_id == conversion.id, Requirement.deleted.is_(False))
            .order_by(Requirement.order)
        )
    )
    return render(
        request,
        "partials/table.html",
        {
            "conversion": conversion,
            "requirements": requirements,
            "segment_text": _segment_text(session, conversion.id),
            "diffs": {r.id: changed_fields(r) for r in requirements},
            "methods": VERIF_METHODS,
            "stages": VERIF_STAGES,
            "classifications": CLASSIFICATIONS,
        },
    )


@router.post("/rida/{requirement_id}")
def update_cell(
    request: Request,
    requirement_id: int,
    field: str = Form(...),
    value: str = Form(""),
    session: Session = Depends(get_db),
):
    if field not in EDITABLE_FIELDS:
        raise HTTPException(status_code=400, detail="Tundmatu väli")
    requirement = _get_requirement(session, requirement_id)

    cleaned = (value or "").strip()
    allowed = ALLOWED_VALUES.get(field)
    if allowed is not None and cleaned not in allowed:
        raise HTTPException(status_code=400, detail=f"Lubamatu väärtus väljal {field}")

    if getattr(requirement, field) != cleaned:
        setattr(requirement, field, cleaned)
        requirement.edited_by_user = True
    session.flush()
    return _row_response(request, session, requirement)


@router.post("/k/{conversion_id}/rida")
def add_row(request: Request, conversion_id: int, session: Session = Depends(get_db)):
    conversion = session.get(Conversion, conversion_id)
    if conversion is None:
        raise HTTPException(status_code=404, detail="Konversiooni ei leitud")
    last = session.scalars(
        select(Requirement)
        .where(Requirement.conversion_id == conversion_id)
        .order_by(Requirement.order.desc())
        .limit(1)
    ).first()
    requirement = Requirement(
        conversion_id=conversion_id,
        order=(last.order + 1) if last else 0,
        category=last.category if last else "",
        description="",
        classification="M",
        added_by_hand=True,
        source_segments=[],
    )
    session.add(requirement)
    session.flush()
    return _table_response(request, session, conversion)


@router.post("/rida/{requirement_id}/kustuta")
def delete_row(request: Request, requirement_id: int, session: Session = Depends(get_db)):
    requirement = _get_requirement(session, requirement_id)
    conversion = requirement.conversion
    requirement.deleted = True
    requirement.deleted_at = datetime.now(timezone.utc)
    session.flush()
    return _table_response(request, session, conversion)


@router.post("/rida/{requirement_id}/liiguta")
def move_row(
    request: Request,
    requirement_id: int,
    direction: str = Form("up"),
    session: Session = Depends(get_db),
):
    requirement = _get_requirement(session, requirement_id)
    conversion = requirement.conversion
    rows = list(
        session.scalars(
            select(Requirement)
            .where(
                Requirement.conversion_id == requirement.conversion_id,
                Requirement.deleted.is_(False),
            )
            .order_by(Requirement.order)
        )
    )
    index = next((i for i, r in enumerate(rows) if r.id == requirement.id), None)
    if index is not None:
        target = index - 1 if direction == "up" else index + 1
        if 0 <= target < len(rows):
            rows[index], rows[target] = rows[target], rows[index]
            for position, row in enumerate(rows):
                row.order = position
    session.flush()
    return _table_response(request, session, conversion)
