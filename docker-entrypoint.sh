#!/usr/bin/env bash
# Container startup: ensure a session secret, build the corpus on first run, serve.
set -euo pipefail

mkdir -p /app/data

# 1) Session-signing secret. Use SECRET_KEY if provided; otherwise generate one and
#    persist it to the data volume so sessions survive restarts.
if [ -z "${SECRET_KEY:-}" ]; then
  if [ ! -f /app/data/.secret ]; then
    python -c "import secrets; print(secrets.token_urlsafe(32))" > /app/data/.secret
    echo "[entrypoint] generated a new SECRET_KEY (persisted to data/.secret)"
  fi
  export SECRET_KEY="$(cat /app/data/.secret)"
fi

# 2) Build the document corpus if the vector store is empty (first run downloads the
#    embedding models and source documents — a few minutes, one time).
CHUNKS="$(python -c "from app.backend.settings import load_backend_settings as L; from app.backend.vectorstore import VectorStore as V; s=L(); print(V(s.chroma_dir, s.collection_name).count())" 2>/dev/null || echo 0)"
if [ "$CHUNKS" = "0" ]; then
  echo "[entrypoint] corpus is empty — ingesting documents (first run, please wait)..."
  python -m app.backend.ingest --rebuild
else
  echo "[entrypoint] corpus present ($CHUNKS chunks) — skipping ingestion."
fi

# 3) Start the app.
if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "[entrypoint] NOTE: GROQ_API_KEY not set — the chatbot will use stub answers. Set it in .env for real answers."
fi
echo "[entrypoint] starting server on http://0.0.0.0:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
