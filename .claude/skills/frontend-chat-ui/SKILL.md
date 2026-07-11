---
name: frontend-chat-ui
description: How the Floor Assistant web app is built and extended — FastAPI + Jinja2 + vanilla JS, email/JWT auth with roles, signup + admin console, persistent chat sessions, theming, and the chat/feedback contract. Use when changing the UI, auth, roles, sessions, or the /api endpoints.
---

# Frontend web app

Server-rendered FastAPI app with a vanilla-JS client (no build step). Multi-user with roles,
persistent chat history, and a dark/light theme.

## Surfaces
- Pages (Jinja2, `app/templates/`): `login.html` (email login), `signup.html` (request access),
  `chat.html` (sidebar + chat), `admin.html` (user management, admin-only).
- `app/static/js/chat.js` — sessions/history, send flow, safe markdown, citations, confidence,
  feedback gray-out, theme toggle. `admin.js` — user table + approve/deny/role.
- `app/static/css/styles.css` — app shell (sidebar + main), light/dark via `data-theme`
  (manual choice overrides OS `prefers-color-scheme`), feedback `.done` disabled state.

## Backend (`app/main.py`, `app/auth.py`, `app/db.py`, `app/config.py`)
- Auth: email + password, bcrypt, httpOnly JWT cookie (`access_token`) carrying `uid`+`role`.
  `require_user` / `require_admin` deps. Signup → PENDING; login gated on ACTIVE.
- Data: SQLite (`app/db.py`) — users, chat_sessions, chat_messages, feedback. See `backend-rag-agent`.
- `USE_AGENT` (GROQ_API_KEY set) runs the real agent in `/api/chat`; else `app/stub.py`.

## API contracts
`POST /api/chat` `{message, session_id?}` → `{answer(markdown), domain, confidence:{level,score},
citations:[{source_title,section,page,url,snippet}], session_id, message_id, session_title}`.
Creates a session if `session_id` is null. `message_id` is the DB id used for feedback.
`POST /api/feedback` `{message_id, rating:"up"|"down"}` → `{status:"recorded"}` (persisted).
`GET /api/sessions`, `GET /api/sessions/{id}/messages` (includes prior `feedback` state per message),
`GET /api/me`, `GET /api/admin/users`, `POST /api/admin/users/{id}/decision` (admin).

## Conventions / gotchas
- Routes returning a **union** of response types need `response_model=None` on the decorator.
- `chat.js`/`admin.js` escape all text before rendering — never inject model/user output as raw HTML.
- `db.create_user` fetches the row **after** the insert commits (a second SQLite connection can't see
  an uncommitted row) — keep that pattern for any create-then-return method.
- Feedback grays out via the `.done` class (`opacity` + `pointer-events:none`); history reload
  re-applies it from the persisted `feedback` field.
- Preview-server runner can't read the project `.venv`; run uvicorn via a background shell and open
  the browser at that URL.

## Run
`cp .env.example .env`; set `SECRET_KEY`, `ADMIN_PASSWORD` (+ optional `DEMO_PASSWORD`, `GROQ_API_KEY`);
`python -m app.backend.ingest --rebuild` (corpus); `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000`.
Seeded logins: admin `admin@floor.local` / `ADMIN_PASSWORD`, demo employee `supervisor@floor.local` / `DEMO_PASSWORD`.
