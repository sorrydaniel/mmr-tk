"""Shared web helpers: templates, auth check, small formatting filters."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import get_config

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

SESSION_AUTH_KEY = "authenticated"
SESSION_REVIEWER_KEY = "reviewer_code"

# Paths reachable without logging in. /health must answer even when nothing else can.
PUBLIC_PATHS = ("/health", "/login", "/logout", "/favicon.ico")

STATUS_LABELS = {
    "draft": "Mustand",
    "converted": "Teisendatud",
    "failed": "Ebaõnnestus",
    "reviewed": "Üle vaadatud",
}

RUN_STATUS_LABELS = {
    "queued": "Järjekorras",
    "splitting": "Lõikudeks jagamine",
    "calling": "Mudeli päring",
    "validating": "Kontrollimine",
    "done": "Valmis",
    "failed": "Ebaõnnestus",
}

SEGMENT_TYPE_LABELS = {
    "HEADING": "pealkiri",
    "BULLET": "loendipunkt",
    "TABLE_ROW": "tabelirida",
    "SENTENCE": "lause",
}

CATEGORY_SOURCE_LABELS = {
    "MMR_HEADING": "",
    "DEFAULT_LIST": "loendist",
    "NEW": "uus",
}


def et_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


def et_date(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%d.%m.%Y")


def et_number(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".replace(".", ",")


templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.filters["et_datetime"] = et_datetime
templates.env.filters["et_date"] = et_date
templates.env.filters["et_number"] = et_number
templates.env.globals["status_labels"] = STATUS_LABELS
templates.env.globals["run_status_labels"] = RUN_STATUS_LABELS
templates.env.globals["segment_type_labels"] = SEGMENT_TYPE_LABELS
templates.env.globals["category_source_labels"] = CATEGORY_SOURCE_LABELS


def is_authenticated(request: Request) -> bool:
    if not get_config().login_required:
        return True
    try:
        return bool(request.session.get(SESSION_AUTH_KEY))
    except AssertionError:  # pragma: no cover - session middleware missing
        return False


def is_public_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in PUBLIC_PATHS)


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    payload = {
        "request": request,
        "mock_mode": get_config().mock_mode,
        "login_required": get_config().login_required,
    }
    payload.update(context or {})
    return templates.TemplateResponse(request, name, payload, status_code=status_code)
