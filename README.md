# Manufacturing Floor Assistant

Agentic RAG chatbot that lets plant floor supervisors ask questions in plain language and get
**accurate, source-grounded answers with citations and a confidence score**, routed to the right
documentation domain — **safety procedures**, **maintenance manuals**, or **quality-control standards**.

See [docs/architecture.md](docs/architecture.md) for the full design, stack rationale, and diagrams.

## Status
- ✅ Architecture designed and approved
- ✅ Frontend vertical slice — login, chat UI, citations, confidence, feedback (runs against a stub)
- ⏳ Backend (LangGraph agent, retrieval, guardrails) — next
- ⏳ Wiring frontend to the real agent

## Run the frontend (current slice)

Requires Python 3.12+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# In .env, set:
#   SECRET_KEY    -> python -c "import secrets; print(secrets.token_urlsafe(32))"
#   DEMO_PASSWORD -> any dev password (e.g. floor123)

.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000 and sign in with `supervisor` / your `DEMO_PASSWORD`.

The app currently answers from `app/stub.py` (canned, correctly-shaped responses) so the UI is fully
explorable before the backend exists. The `/api/chat` response shape is the contract the real agent
will fulfill — see [.claude/skills/frontend-chat-ui/SKILL.md](.claude/skills/frontend-chat-ui/SKILL.md).

## Configuration
All config comes from environment variables (`.env`, gitignored). The app **fails fast** with a clear
message if a required variable is missing. Secrets are never committed. See `.env.example`.
