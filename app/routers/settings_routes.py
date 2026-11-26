"""Settings.

Anything the engineer is expected to tune lives here rather than in code: the system
prompt, the verification mapping table, the classification fill colours. Two of those
colours are deliberately empty -- they are unknown until a real filled TK is opened, and
an empty value simply paints nothing.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import settings_store
from app.db import get_db
from app.models import PROCUREMENT_PROFILES, REQUIREMENT_TYPES, Conversion
from app.web import render

router = APIRouter()


def _page(request: Request, session: Session, message: str | None, error: str | None):
    values = settings_store.get_all(session)
    try:
        mapping = json.loads(values[settings_store.VERIF_MAPPING])
    except (KeyError, json.JSONDecodeError):
        mapping = settings_store.DEFAULT_VERIF_MAPPING
    try:
        categories = json.loads(values[settings_store.DEFAULT_CATEGORIES])
    except (KeyError, json.JSONDecodeError):
        categories = settings_store.DEFAULT_CATEGORY_LIST

    return render(
        request,
        "settings.html",
        {
            "conversions": list(
                session.scalars(select(Conversion).order_by(desc(Conversion.created_at)))
            ),
            "selected": None,
            "values": values,
            "mapping": mapping,
            "categories": categories,
            "profiles": PROCUREMENT_PROFILES,
            "requirement_types": REQUIREMENT_TYPES,
            "default_prompt": settings_store.default_system_prompt(),
            "message": message,
            "error": error,
        },
    )


@router.get("/seaded")
def settings_page(request: Request, session: Session = Depends(get_db)):
    return _page(request, session, None, None)


@router.post("/seaded")
async def save_settings(request: Request, session: Session = Depends(get_db)):
    form = await request.form()
    error: str | None = None

    if form.get("action") == "reset_prompt":
        settings_store.set_value(
            session, settings_store.SYSTEM_PROMPT, settings_store.default_system_prompt()
        )
        session.commit()
        return _page(request, session, "Süsteemipromptide vaikeversioon taastatud.", None)

    simple_keys = (
        settings_store.MODEL,
        settings_store.TEMPERATURE,
        settings_store.SYSTEM_PROMPT,
        settings_store.CLASS_FILL_M,
        settings_store.CLASS_FILL_N,
        settings_store.CLASS_FILL_I,
        settings_store.CLASS_FILL_OP,
        settings_store.UNCERTAIN_FILL,
        settings_store.GROUP_ROW_LABEL,
    )
    for key in simple_keys:
        if key in form:
            value = str(form.get(key) or "").strip()
            if key.startswith("class_fill") or key == settings_store.UNCERTAIN_FILL:
                value = value.upper().lstrip("#")
                if value and (len(value) not in (6, 8) or not all(
                    c in "0123456789ABCDEF" for c in value
                )):
                    error = f"Värvikood '{value}' ei ole korrektne ARGB/RGB hex."
                    continue
                if len(value) == 6 and value:
                    value = "FF" + value
            settings_store.set_value(session, key, value)

    if settings_store.DEFAULT_CATEGORIES in form:
        raw = str(form.get(settings_store.DEFAULT_CATEGORIES) or "")
        items = [line.strip() for line in raw.splitlines() if line.strip()]
        settings_store.set_json(session, settings_store.DEFAULT_CATEGORIES, items)

    # Verification mapping arrives as map__<PROFILE>__<TYPE>__<field>
    mapping_updates: dict[str, dict[str, dict[str, str]]] = {}
    for key, value in form.multi_items():
        if not key.startswith("map__"):
            continue
        parts = key.split("__")
        if len(parts) != 4:
            continue
        _, profile, requirement_type, field = parts
        if profile not in PROCUREMENT_PROFILES or requirement_type not in REQUIREMENT_TYPES:
            continue
        if field not in ("method", "stage", "with_bid"):
            continue
        mapping_updates.setdefault(profile, {}).setdefault(requirement_type, {})[field] = str(
            value
        ).strip()

    if mapping_updates:
        current = settings_store.get_json(session, settings_store.VERIF_MAPPING) or {}
        for profile, types in mapping_updates.items():
            for requirement_type, fields in types.items():
                current.setdefault(profile, {}).setdefault(requirement_type, {}).update(fields)
        settings_store.set_json(session, settings_store.VERIF_MAPPING, current)

    if settings_store.HINDA_SHOW_HINTS in form:
        settings_store.set_value(
            session,
            settings_store.HINDA_SHOW_HINTS,
            "true" if form.get(settings_store.HINDA_SHOW_HINTS) in ("on", "true", "1") else "false",
        )

    session.commit()
    return _page(request, session, None if error else "Seaded salvestatud.", error)
