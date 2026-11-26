"""Environment configuration.

Deliberately tolerant: a missing or broken DATABASE_URL must not prevent the app from
booting, otherwise the friendly Estonian database error page can never be rendered.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-5-5"

# Max tokens for the model response. ~80 TK rows of verbose JSON needs real headroom.
MAX_OUTPUT_TOKENS = 20000

# Design limit from SPEC.md. Above this the user gets a warning, never silent truncation.
MAX_SEGMENTS = 150

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def normalise_database_url(raw: str | None) -> str | None:
    """Railway hands out postgresql:// ; SQLAlchemy needs an explicit psycopg driver."""
    if not raw:
        return None
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@dataclass(frozen=True)
class Config:
    database_url: str | None
    anthropic_api_key: str | None
    anthropic_model: str
    app_password: str | None
    secret_key: str

    @property
    def mock_mode(self) -> bool:
        return not self.anthropic_api_key

    @property
    def login_required(self) -> bool:
        return bool(self.app_password)


def load_config() -> Config:
    return Config(
        database_url=normalise_database_url(os.environ.get("DATABASE_URL")),
        anthropic_api_key=(os.environ.get("ANTHROPIC_API_KEY") or "").strip() or None,
        anthropic_model=(os.environ.get("ANTHROPIC_MODEL") or "").strip() or DEFAULT_MODEL,
        app_password=(os.environ.get("APP_PASSWORD") or "").strip() or None,
        secret_key=(os.environ.get("SECRET_KEY") or "").strip() or secrets.token_urlsafe(32),
    )


config = load_config()


def get_config() -> Config:
    """Always read through this, never through a module-level import of `config`.

    Tests change APP_PASSWORD and ANTHROPIC_API_KEY after import; a direct
    `from app.config import config` would keep handing out the stale object.
    """
    return config


def reload_config() -> Config:
    global config
    config = load_config()
    return config
