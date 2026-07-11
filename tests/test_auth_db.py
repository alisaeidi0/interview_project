"""Tests for the SQLite data layer and auth flow (signup, roles, sessions, feedback).

Uses a temp DB — no network, no Groq. Expected behaviors are the documented rules:
signups start PENDING and cannot log in until an admin approves; approval sets the
granted role; feedback and messages persist and are scoped to their owner.
"""

from __future__ import annotations

import pytest

from app.auth import AuthError, authenticate, hash_password, signup
from app.db import (
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    STATUS_ACTIVE,
    STATUS_DENIED,
    Database,
)


@pytest.fixture()
def db(tmp_path) -> Database:
    return Database(str(tmp_path / "test.db"))


def test_signup_creates_pending_user(db):
    user = signup(db, "a@x.com", "Ann", "secret123", ROLE_EMPLOYEE)
    assert user["status"] == "pending"
    assert user["requested_role"] == ROLE_EMPLOYEE
    assert user["role"] is None  # not granted until approved


def test_duplicate_email_rejected(db):
    signup(db, "a@x.com", "Ann", "secret123", ROLE_EMPLOYEE)
    with pytest.raises(AuthError):
        signup(db, "a@x.com", "Other", "secret123", ROLE_EMPLOYEE)


def test_short_password_rejected(db):
    with pytest.raises(AuthError):
        signup(db, "b@x.com", "Bo", "123", ROLE_EMPLOYEE)


def test_pending_user_cannot_login_then_can_after_approval(db):
    u = signup(db, "c@x.com", "Cy", "secret123", ROLE_EMPLOYEE)
    with pytest.raises(AuthError, match="awaiting admin approval"):
        authenticate(db, "c@x.com", "secret123")

    db.decide_user(u["id"], status=STATUS_ACTIVE, role=ROLE_EMPLOYEE, admin_id=1)
    user = authenticate(db, "c@x.com", "secret123")
    assert user.role == ROLE_EMPLOYEE
    assert not user.is_admin


def test_denied_user_cannot_login(db):
    u = signup(db, "d@x.com", "Di", "secret123", ROLE_EMPLOYEE)
    db.decide_user(u["id"], status=STATUS_DENIED, role=None, admin_id=1)
    with pytest.raises(AuthError):
        authenticate(db, "d@x.com", "secret123")


def test_admin_role_grants_is_admin(db):
    db.create_user(
        email="admin@x.com", name="Boss", password_hash=hash_password("secret123"),
        requested_role=ROLE_ADMIN, status=STATUS_ACTIVE, role=ROLE_ADMIN,
    )
    user = authenticate(db, "admin@x.com", "secret123")
    assert user.is_admin


def test_wrong_password_rejected(db):
    db.create_user(
        email="e@x.com", name="Ed", password_hash=hash_password("secret123"),
        requested_role=ROLE_EMPLOYEE, status=STATUS_ACTIVE, role=ROLE_EMPLOYEE,
    )
    with pytest.raises(AuthError, match="Invalid email or password"):
        authenticate(db, "e@x.com", "wrongpass")


def test_sessions_and_messages_persist_scoped_to_owner(db):
    owner = db.create_user(
        email="f@x.com", name="Fi", password_hash=hash_password("secret123"),
        requested_role=ROLE_EMPLOYEE, status=STATUS_ACTIVE, role=ROLE_EMPLOYEE,
    )
    s = db.create_session(owner["id"], "First chat")
    db.add_message(s["id"], "user", "How do I lock out a machine?")
    db.add_message(s["id"], "assistant", "Apply LOTO devices.", meta={"domain": "safety"})

    assert len(db.list_messages(s["id"])) == 2
    # A different user cannot fetch someone else's session.
    assert db.get_session(s["id"], user_id=owner["id"] + 999) is None
    assert db.get_session(s["id"], user_id=owner["id"]) is not None


def test_feedback_is_recorded_once_and_updatable(db):
    owner = db.create_user(
        email="g@x.com", name="Gu", password_hash=hash_password("secret123"),
        requested_role=ROLE_EMPLOYEE, status=STATUS_ACTIVE, role=ROLE_EMPLOYEE,
    )
    s = db.create_session(owner["id"], "chat")
    a = db.add_message(s["id"], "assistant", "Answer", meta={"domain": "safety"})
    db.add_feedback(a["id"], owner["id"], "up", "Q", "Answer")
    assert db.get_feedback(a["id"])["rating"] == "up"
    # One row per message: changing the rating updates in place.
    db.add_feedback(a["id"], owner["id"], "down", "Q", "Answer")
    assert db.get_feedback(a["id"])["rating"] == "down"
