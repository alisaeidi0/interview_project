# Manufacturing Floor Assistant

An agentic RAG chatbot that lets plant-floor supervisors ask questions in plain language and get
**accurate, source-grounded answers with citations and a confidence score**, automatically routed to
the right documentation domain — **safety procedures**, **maintenance manuals**, or
**quality-control standards**.

Built with FastAPI + a LangGraph agent on open-source LLMs (Groq), local embeddings + re-ranking,
ChromaDB, and SQLite. Full design and diagrams: [docs/architecture.md](docs/architecture.md).

---

## Run it (3 steps, ~5 minutes)

**Before you start:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and
open it (wait until it says "Docker Desktop is running"). That's the only tool you need — you do
**not** need Python, Node, or anything else installed.

Copy-paste these into a terminal:

```bash
# 1. Get the code
git clone https://github.com/alisaeidi0/interview_project.git
cd interview_project

# 2. Create your settings file (it works as-is)
cp .env.example .env

# 3. Start the app
docker compose up --build
```

When you see `[entrypoint] starting server on http://0.0.0.0:8000`, open **http://localhost:8000**
in your browser and sign in with the demo accounts below.

- **First run takes a few minutes** — it downloads the AI models and documents and builds the search
  index (all automatic). Later starts take seconds.
- **To stop:** press `Ctrl-C`, then optionally `docker compose down`.

> **Want real AI answers?** Add a **free Groq API key** to `.env` (line `GROQ_API_KEY=`) — see
> [Groq API key](#groq-api-key) below. **Without a key the app still runs** and returns canned
> answers, so you can explore the whole interface either way.

### Default logins

| Role         | Email                    | Password   | Can do                                   |
|--------------|--------------------------|------------|------------------------------------------|
| **Admin**    | `admin@floor.local`      | `admin123` | Everything, plus approve users & roles   |
| **Employee** | `supervisor@floor.local` | `floor123` | Chatbot + read access                    |

> Change `ADMIN_PASSWORD` / `DEMO_PASSWORD` in `.env` before sharing with a real team.

### Try it end to end
1. Open http://localhost:8000 → **Request access** → sign up with a name, email, role.
2. Sign in as **admin** → **Admin console** → **approve** the new request (and set its role).
3. Sign in as the new user → ask a question (e.g. *"How do I verify zero energy before servicing?"*).
   You'll get a routed, cited answer. Give it a 👍/👎 — feedback is stored.
4. Toggle **dark/light** in the sidebar; your chats are saved in **Chat history**.

---

## Groq API key

The chatbot's LLM runs on [GroqCloud](https://groq.com) (open-source models like Llama 3.3, plus the
Prompt Guard and safeguard models used for guardrails).

1. Sign in at **https://console.groq.com/keys** and create a key (free tier available).
2. Paste it into `.env`: `GROQ_API_KEY=gsk_...`
3. Restart: `docker compose up` (or `docker compose restart`).

Without a key the app still runs, but answers come from a built-in **stub** so you can explore the UI.

---

## Configuration (`.env`)

| Variable                     | Required | Default                  | Purpose                                             |
|------------------------------|----------|--------------------------|-----------------------------------------------------|
| `GROQ_API_KEY`               | for real answers | —                | Groq API key; stub answers if unset                 |
| `SECRET_KEY`                 | no       | auto-generated           | JWT session signing (container generates & persists)|
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | yes  | `admin@floor.local` / `admin123` | Seeded admin account                    |
| `DEMO_EMAIL` / `DEMO_PASSWORD`   | no   | `supervisor@floor.local` / `floor123` | Optional demo employee            |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| no       | `480`                    | Session lifetime                                    |
| `GROQ_MODEL`                 | no       | `llama-3.3-70b-versatile`| Generation model                                    |

Secrets live only in `.env` (gitignored) — they are never committed or baked into the image.

---

## Run without Docker (local Python)

Requires **Python 3.12+**.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# set SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(32))"),
# ADMIN_PASSWORD, and GROQ_API_KEY in .env

# Build the document corpus once (downloads models + source PDFs):
.venv/bin/python -m app.backend.ingest --rebuild

# Run:
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
set -a; . ./.env; set +a          # load env
.venv/bin/python -m pytest tests/
```

Retrieval/agent tests assert real behavior against the corpus and skip cleanly if the corpus isn't
built or `GROQ_API_KEY` isn't set, so the offline unit suite always runs.

---

## How it works (short version)

```
Question → Input guard (injection) → Route (safety|maintenance|QC)
        → Retrieve (vector + similarity gate + cross-encoder re-rank)
        → Generate grounded answer + citations (Groq, temp 0)
        → Groundedness judge → Output safety → Answer + confidence
```

- **Local & free on the hot path:** embeddings (`bge-small`) and re-ranking (`bge-reranker`) run
  in-process — no API calls, no rate limits. Only generation/judging/guarding use Groq.
- **Grounded, not guessed:** answers are constrained to retrieved passages, cite their source
  (title · section · page), and carry a confidence score. If nothing relevant is found, it refuses.
- **Explainable:** every step is a logged node in a LangGraph graph.

See [docs/architecture.md](docs/architecture.md) for the full architecture and rationale.

## Project structure

```
app/
  main.py            FastAPI: auth, signup, admin, chat, sessions, feedback
  auth.py  db.py     Email/JWT auth with roles; SQLite (users, sessions, messages, feedback)
  templates/ static/ Login, signup, chat (sidebar), admin console; CSS/JS (no build step)
  backend/           RAG: ingest, chunking, embeddings, vectorstore, retriever, router,
                     judge, guardrails, agent (LangGraph)
docs/architecture.md Architecture, diagrams, data sources
tests/               pytest suite
Dockerfile  docker-compose.yml  docker-entrypoint.sh
```

## Data & licensing

The corpus is built from **real, legally-usable** documents, downloaded at ingest time (not committed):
- **Public domain (US gov):** OSHA 3120 (Lockout/Tagout), OSHA 3170 (machine guarding), NIST/SEMATECH
  SPC handbook.
- **Manufacturer manual (free to download, copyright retained):** Baldor MN416 motor manual — used for
  the internal prototype only; do not redistribute.

Sources and their licenses are tracked in [app/backend/sources.py](app/backend/sources.py).

## Troubleshooting

- **Port 8000 in use:** change the mapping in `docker-compose.yml` (e.g. `"8080:8000"`).
- **First run is slow / seems stuck:** it's downloading models + documents; watch `docker compose logs -f`.
- **Answers say "stub"/generic:** `GROQ_API_KEY` isn't set in `.env` — add it and `docker compose restart`.
- **Rebuild the corpus from scratch:** `docker compose run --rm app python -m app.backend.ingest --rebuild`.
- **Reset all users/chats:** stop the app and delete `data/app.db` (keeps the search index).
