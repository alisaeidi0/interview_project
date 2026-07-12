"""SQLite data layer: users, chat sessions, messages, and feedback.

A file-backed SQLite DB keeps the prototype self-contained (no server/container to
run). The schema mirrors what a Postgres migration would use, so moving to Postgres
later is a driver swap, not a redesign. Connections are opened per operation with a
short timeout and WAL mode, which is safe across FastAPI's threadpool workers.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# Roles and user lifecycle states.
ROLE_ADMIN = "admin"
ROLE_EMPLOYEE = "employee"
VALID_ROLES = {ROLE_ADMIN, ROLE_EMPLOYEE}

STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_DENIED = "denied"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    email          TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    requested_role TEXT NOT NULL,
    role           TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',
    created_at     TEXT NOT NULL,
    decided_at     TEXT,
    decided_by     INTEGER
);
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    meta_json  TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL UNIQUE,
    user_id    INTEGER NOT NULL,
    rating     TEXT NOT NULL,
    question   TEXT,
    answer     TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES chat_messages(id)
);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Database:
    """Thin data-access layer over a SQLite file."""

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # --- Users ---

    def create_user(
        self,
        email: str,
        name: str,
        password_hash: str,
        requested_role: str,
        *,
        status: str = STATUS_PENDING,
        role: str | None = None,
        decided_by: int | None = None,
    ) -> dict[str, Any]:
        """Insert a user. Raises sqlite3.IntegrityError if the email exists."""
        now = _now()
        decided_at = now if status != STATUS_PENDING else None
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO users (email, name, password_hash, requested_role,
                       role, status, created_at, decided_at, decided_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (email.lower().strip(), name.strip(), password_hash, requested_role,
                 role, status, now, decided_at, decided_by),
            )
            new_id = cur.lastrowid
        # Fetch after the INSERT has committed (a fresh connection can't see it before).
        return self.get_user_by_id(new_id)  # type: ignore[arg-type]

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY "
                "CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def count_admins(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM users WHERE role = ? AND status = ?",
                (ROLE_ADMIN, STATUS_ACTIVE),
            ).fetchone()
        return int(row["n"])

    def decide_user(
        self, user_id: int, *, status: str, role: str | None, admin_id: int
    ) -> dict[str, Any] | None:
        """Approve/deny a user and set the granted role."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET status = ?, role = ?, decided_at = ?, decided_by = ? "
                "WHERE id = ?",
                (status, role, _now(), admin_id, user_id),
            )
        return self.get_user_by_id(user_id)

    # --- Chat sessions & messages ---

    def create_session(self, user_id: int, title: str) -> dict[str, Any]:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO chat_sessions (user_id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, title[:120], now, now),
            )
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return dict(row)

    def list_sessions(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: int, user_id: int) -> dict[str, Any] | None:
        """Fetch a session scoped to its owner (prevents cross-user access)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def add_message(
        self, session_id: int, role: str, content: str, meta: dict | None = None
    ) -> dict[str, Any]:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, meta_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, json.dumps(meta) if meta else None, now),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id)
            )
            row = conn.execute(
                "SELECT * FROM chat_messages WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return dict(row)

    def rename_session(self, session_id: int, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE chat_sessions SET title = ? WHERE id = ?", (title[:120], session_id)
            )

    def list_messages(self, session_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_message(self, message_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT m.*, s.user_id AS owner_id FROM chat_messages m "
                "JOIN chat_sessions s ON s.id = m.session_id WHERE m.id = ?",
                (message_id,),
            ).fetchone()
        return dict(row) if row else None

    # --- Feedback ---

    def add_feedback(
        self, message_id: int, user_id: int, rating: str, question: str, answer: str
    ) -> None:
        """Record thumbs feedback with the surrounding messages. One per message."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO feedback (message_id, user_id, rating, question, answer, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(message_id) DO UPDATE SET rating = excluded.rating, "
                "created_at = excluded.created_at",
                (message_id, user_id, rating, question, answer, _now()),
            )

    def get_feedback(self, message_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM feedback WHERE message_id = ?", (message_id,)
            ).fetchone()
        return dict(row) if row else None
