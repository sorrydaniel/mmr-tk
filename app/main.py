"""Application entry point.

Two things matter here beyond wiring. An unreachable database must render a friendly
Estonian page rather than a stack trace, because the deployment target is a managed
Postgres that can be asleep or rotating credentials. And `/health` must answer 200 without
touching the database, or the platform health check will kill a container that is merely
waiting for its database.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, get_config
from app.db import DatabaseUnavailable, session_scope
from app.routers import auth, conversions, requirements, runs, settings_routes
from app.seed import seed_all
from app.web import is_authenticated, is_public_path, render

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="MMR → TK konverter", docs_url=None, redoc_url=None)


async def require_login(request: Request, call_next):
    if get_config().login_required and not is_public_path(request.url.path):
        if not is_authenticated(request):
            if request.headers.get("HX-Request"):
                return Response(status_code=401, headers={"HX-Redirect": "/login"})
            # Relative on purpose. An absolute URL built from the request would carry the
            # scheme the app sees, which behind a TLS-terminating proxy is http.
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


# Order matters, and it is the reverse of what it looks like: Starlette makes the
# LAST-added middleware the OUTERMOST one. The session must be established before the
# login check reads it, so SessionMiddleware is added last. Adding it first put the auth
# check outside it, where request.session raises and every login looked like a failure.
app.add_middleware(BaseHTTPMiddleware, dispatch=require_login)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_config().secret_key,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=get_config().session_https_only,
    # No domain is set on purpose: the cookie then belongs to the exact host that served
    # it, which is what a single Railway URL wants.
)


def assert_session_before_auth() -> None:
    """Fail loudly rather than redirect silently if that ordering is ever reversed."""
    names = [m.cls.__name__ for m in app.user_middleware]
    if "SessionMiddleware" not in names:
        raise RuntimeError("SessionMiddleware puudub rakenduse vahevara hulgast.")
    if names.index("SessionMiddleware") > names.index("BaseHTTPMiddleware"):
        raise RuntimeError(
            "SessionMiddleware peab olema väliseim: autentimise kontroll loeb sessiooni. "
            f"Praegune järjekord (väliseim esimesena): {names}"
        )


@app.on_event("startup")
def on_startup() -> None:
    """Seed defaults and fail any run that died with the previous process."""
    assert_session_before_auth()

    cfg = get_config()
    if cfg.ephemeral_sessions:
        logger.critical(
            "SECRET_KEY puudub, aga APP_PASSWORD on seatud: sessiooni võti luuakse igal "
            "käivitusel uuesti, nii et iga taaskäivitus logib kõik välja ja mitme "
            "tööprotsessi korral sisselogimine ei tööta üldse. Sea SECRET_KEY."
        )
    if not cfg.login_required:
        logger.warning("APP_PASSWORD puudub: rakendus on avalikult ligipääsetav.")

    try:
        from app.runner import recover_orphaned_runs

        session = session_scope()
        try:
            recover_orphaned_runs(session)
            result = seed_all(session)
            logger.info("Startup seeding: %s", result)
        finally:
            session.close()
    except (DatabaseUnavailable, SQLAlchemyError) as exc:
        # Not fatal: the app still boots and shows the database error page.
        logger.error("Startup seeding skipped, database unavailable: %s", exc)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable):
    logger.error("Database unavailable: %s", exc)
    return render(request, "error_db.html", {"detail": str(exc)}, status_code=503)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error")
    return render(
        request,
        "error_db.html",
        {"detail": type(exc).__name__},
        status_code=503,
    )


app.include_router(auth.router)
app.include_router(conversions.router)
app.include_router(requirements.router)
app.include_router(runs.router)
app.include_router(settings_routes.router)
