"""Authentication: password hashing, JWT session tokens, and a seeded demo user.

This is a prototype user store (a single seeded supervisor account held in memory).
The token/cookie machinery is real so it swaps cleanly for a Postgres-backed user
table later without changing the frontend or route contracts.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import bcrypt
import jwt

from app.config import Settings


@dataclass(frozen=True)
class User:
    """An authenticated user and their role."""

    username: str
    role: str


class UserStore:
    """In-memory user store seeded with a single demo supervisor.

    Passwords are stored only as bcrypt hashes, never in plaintext.
    """

    def __init__(self, username: str, password: str, role: str = "supervisor") -> None:
        self._username = username
        self._role = role
        self._password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    def authenticate(self, username: str, password: str) -> User | None:
        """Return the User on valid credentials, else None."""
        if username != self._username:
            return None
        if not bcrypt.checkpw(password.encode("utf-8"), self._password_hash):
            return None
        return User(username=self._username, role=self._role)


def create_access_token(user: User, settings: Settings) -> str:
    """Mint a signed JWT for the given user."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> User | None:
    """Validate a JWT and return the User, or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
    username = payload.get("sub")
    role = payload.get("role", "supervisor")
    if not username:
        return None
    return User(username=username, role=role)
