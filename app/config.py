"""Application configuration, loaded from environment variables.

Fails fast and clearly when required config is missing, rather than deep into a
request. Secrets never have code defaults — they must come from the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # load .env if present; real env vars still take precedence


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
    demo_username: str
    demo_password: str
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
        demo_username=os.environ.get("DEMO_USERNAME", "supervisor"),
        demo_password=_require("DEMO_PASSWORD"),
    )
