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
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_config
from app.db import DatabaseUnavailable, session_scope
from app.routers import auth, conversions, requirements, runs, settings_routes
from app.seed import seed_all
from app.web import is_authenticated, is_public_path, render

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="MMR → TK konverter", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=get_config().secret_key, same_site="lax")


@app.middleware("http")
async def require_login(request: Request, call_next):
    if get_config().login_required and not is_public_path(request.url.path):
        if not is_authenticated(request):
            if request.headers.get("HX-Request"):
                return Response(status_code=401, headers={"HX-Redirect": "/login"})
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    """Seed defaults and fail any run that died with the previous process."""
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
