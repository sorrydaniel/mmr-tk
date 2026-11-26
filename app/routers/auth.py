"""One shared password, one session cookie.

The deployment URL is public, so without this anyone who finds it can spend API credits.
It is deliberately not a user system: nothing here stores an identity, and the research
data is attributed by an anonymous reviewer code instead.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_config
from app.web import SESSION_AUTH_KEY, render, session_of

router = APIRouter()


def _page(request: Request, error: str | None, status_code: int = 200):
    return render(
        request,
        "login.html",
        {"error": error, "ephemeral_sessions": get_config().ephemeral_sessions},
        status_code=status_code,
    )


@router.get("/login")
def login_form(request: Request):
    if not get_config().login_required:
        return RedirectResponse("/", status_code=303)
    return _page(request, None)


@router.post("/login")
def login(request: Request, password: str = Form("")):
    cfg = get_config()
    if not cfg.login_required:
        return RedirectResponse("/", status_code=303)
    expected = cfg.app_password or ""
    if secrets.compare_digest(password.encode(), expected.encode()):
        session_of(request)[SESSION_AUTH_KEY] = True
        # Relative on purpose: an absolute URL would carry the scheme the app sees, and
        # behind a TLS-terminating proxy that is http.
        return RedirectResponse("/", status_code=303)
    return _page(request, "Vale parool.", status_code=401)


@router.post("/logout")
def logout(request: Request):
    session_of(request).clear()
    return RedirectResponse("/login" if get_config().login_required else "/", status_code=303)
