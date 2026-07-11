---
name: frontend-chat-ui
description: How the Floor Assistant frontend is built and extended — FastAPI + Jinja2 + vanilla JS chat UI, JWT cookie auth, and the chat/feedback response contract. Use when changing the UI, adding a chat feature, adjusting auth, or wiring the real backend into the existing /api/chat endpoint.
---

# Frontend chat UI

Server-rendered FastAPI app with a vanilla-JS chat client. No build step, no npm — matches the
"HTML/CSS/FastAPI" stack. The UI talks to two JSON endpoints whose shapes are the contract the real
backend must honor, so the agent can be dropped in without touching the frontend.

## Layout
- `app/main.py` — routes: `/login` (GET/POST), `/logout`, `/chat` (protected page), `/api/chat`,
  `/api/feedback`, `/healthz`. Auth via httpOnly JWT cookie (`access_token`).
- `app/config.py` — env-driven `Settings`; **fails fast** if `SECRET_KEY` / `DEMO_PASSWORD` missing.
- `app/auth.py` — bcrypt hashing, JWT mint/verify, in-memory seeded user (`UserStore`).
- `app/stub.py` — canned, correctly-shaped answers for UI experimentation. **Replace this module**
  with the LangGraph agent; keep the return shape identical.
- `app/templates/` — `login.html`, `chat.html` (Jinja2).
- `app/static/css/styles.css` — light/dark aware, no external assets.
- `app/static/js/chat.js` — send flow, safe minimal markdown, citations, confidence, feedback.

## Response contract (`POST /api/chat` → JSON)
```json
{
  "answer": "markdown string (bold, ordered/unordered lists supported)",
  "domain": "safety | maintenance | quality_control | unrouted",
  "confidence": { "level": "high | medium | low", "score": 0.0-1.0 },
  "citations": [
    { "source_title": "...", "section": "...", "page": 12, "url": "https://...", "snippet": "..." }
  ]
}
```
`POST /api/feedback` accepts `{ message_id, rating: "up"|"down", question }` → `{ "status": "recorded" }`.

## Wiring the real backend (later)
Swap `app.stub.answer()` for the LangGraph agent call inside `api_chat`. Return the same dict shape.
`domain` drives the badge color/label (see `DOMAIN_LABELS` in chat.js + `.domain-*` in CSS); an
`unrouted`/low-confidence result hides the badge and shows the fallback text — that's the evidence-gate
UX. Persist feedback to Postgres in `api_feedback` (currently logged only).

## Conventions / gotchas
- Routes returning a **union** of response types (e.g. `HTMLResponse | RedirectResponse`) need
  `response_model=None` on the decorator, or FastAPI errors at import time.
- `chat.js` escapes all text before rendering; keep the markdown renderer minimal and escape-first —
  never inject model output as raw HTML.
- The preview-server runner can't read the project `.venv` (sandbox); run uvicorn via a background
  shell (`.venv/bin/uvicorn app.main:app --port 8000`) and open the browser at that URL instead.

## Run
See README. `cp .env.example .env`, set `SECRET_KEY` + `DEMO_PASSWORD`, then
`.venv/bin/uvicorn app.main:app --port 8000`. Demo login: `supervisor` / value of `DEMO_PASSWORD`.
