"""Application configuration, loaded from environment variables.

Fails fast and clearly when required config is missing, rather than deep into a
request. Secrets never have code defaults — they must come from the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # load .env if present; real env vars still take precedence

REPO_ROOT = Path(__file__).resolve().parents[1]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _require(name: str) -> str:
    """Return a required environment variable or fail fast with a clear message."""
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and set it (see README)."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """Immutable application settings resolved from the environment."""

    secret_key: str
    access_token_expire_minutes: int
    db_path: str
    # Seed accounts (created on first startup if absent).
    admin_email: str
    admin_name: str
    admin_password: str
    demo_email: str | None
    demo_password: str | None
    jwt_algorithm: str = "HS256"


def load_settings() -> Settings:
    """Build Settings from the environment, failing fast on missing values."""
    expire_raw = os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480")
    try:
        expire_minutes = int(expire_raw)
    except ValueError as exc:
        raise ConfigError(
            f"ACCESS_TOKEN_EXPIRE_MINUTES must be an integer, got {expire_raw!r}."
        ) from exc

    return Settings(
        secret_key=_require("SECRET_KEY"),
        access_token_expire_minutes=expire_minutes,
        db_path=os.environ.get("APP_DB_PATH", str(REPO_ROOT / "data" / "app.db")),
        admin_email=os.environ.get("ADMIN_EMAIL", "admin@floor.local"),
        admin_name=os.environ.get("ADMIN_NAME", "Plant Admin"),
        admin_password=_require("ADMIN_PASSWORD"),
        # Optional demo employee — seeded only when DEMO_PASSWORD is set.
        demo_email=os.environ.get("DEMO_EMAIL", "supervisor@floor.local"),
        demo_password=os.environ.get("DEMO_PASSWORD"),
    )
