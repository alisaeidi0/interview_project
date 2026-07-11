"""Authentication: password hashing, JWT session tokens, and account seeding.

Users live in SQLite (see app.db). Only ACTIVE users may sign in; PENDING users
await admin approval and DENIED users are rejected. The JWT carries the user id,
email, and granted role so authorization checks need no extra DB hit.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass

import bcrypt
import jwt

from app.config import Settings
from app.db import (
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    STATUS_ACTIVE,
    STATUS_PENDING,
    VALID_ROLES,
    Database,
)


@dataclass(frozen=True)
class User:
    """An authenticated user resolved from a session token."""

    id: int
    email: str
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


class AuthError(Exception):
    """Raised on a login problem, with a user-facing message."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def signup(
    db: Database, email: str, name: str, password: str, requested_role: str
) -> dict:
    """Create a PENDING account. Raises AuthError on bad input or duplicate email."""
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise AuthError("Please enter a valid email address.")
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    if requested_role not in VALID_ROLES:
        raise AuthError("Please choose a valid role.")
    try:
        return db.create_user(
            email=email,
            name=name,
            password_hash=hash_password(password),
            requested_role=requested_role,
        )
    except sqlite3.IntegrityError as exc:
        raise AuthError("An account with that email already exists.") from exc


def authenticate(db: Database, email: str, password: str) -> User:
    """Return the User on valid credentials + active status, else raise AuthError."""
    record = db.get_user_by_email(email)
    if not record or not verify_password(password, record["password_hash"]):
        raise AuthError("Invalid email or password.")
    if record["status"] == STATUS_PENDING:
        raise AuthError("Your account is awaiting admin approval.")
    if record["status"] != STATUS_ACTIVE:
        raise AuthError("Your account is not active. Contact an administrator.")
    return User(
        id=record["id"], email=record["email"], name=record["name"], role=record["role"]
    )


def create_access_token(user: User, settings: Settings) -> str:
    """Mint a signed JWT for the given user."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user.email,
        "uid": user.id,
        "name": user.name,
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
    if not payload.get("uid") or not payload.get("sub"):
        return None
    return User(
        id=payload["uid"],
        email=payload["sub"],
        name=payload.get("name", ""),
        role=payload.get("role", ROLE_EMPLOYEE),
    )


def seed_accounts(db: Database, settings: Settings) -> None:
    """Create the initial admin (and optional demo employee) if they don't exist."""
    if not db.get_user_by_email(settings.admin_email):
        db.create_user(
            email=settings.admin_email,
            name=settings.admin_name,
            password_hash=hash_password(settings.admin_password),
            requested_role=ROLE_ADMIN,
            status=STATUS_ACTIVE,
            role=ROLE_ADMIN,
        )
    if settings.demo_password and settings.demo_email:
        if not db.get_user_by_email(settings.demo_email):
            db.create_user(
                email=settings.demo_email,
                name="Floor Supervisor",
                password_hash=hash_password(settings.demo_password),
                requested_role=ROLE_EMPLOYEE,
                status=STATUS_ACTIVE,
                role=ROLE_EMPLOYEE,
            )
