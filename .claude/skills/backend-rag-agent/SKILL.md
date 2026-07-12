---
name: backend-rag-agent
description: How the RAG backend works — ingestion, two-stage retrieval, the LangGraph agent, guardrails, and the confidence score. Use when changing retrieval/ranking, the agent graph, guardrails, the corpus, or the Groq model config.
---

# Backend RAG agent

Grounded question-answering over the manufacturing corpus. All generation runs on
Groq at temperature 0; embeddings and re-ranking run locally (no API, no rate limit).

## Modules (`app/backend/`)
- `sources.py` — the document catalog (doc_id, domain, url, license). Add sources here.
- `ingest.py` — `python -m app.backend.ingest [--rebuild]`: download → `chunking.py`
  (sub-section chunks + page + keyword metadata) → `embeddings.py` (fastembed bge-small)
  → `vectorstore.py` (ChromaDB, one collection, `domain` metadata).
- `retriever.py` — two-stage: dense search + **similarity floor (the evidence gate)**,
  then cross-encoder **re-rank** (orders survivors; NOT a zero-threshold gate — bge-reranker
  logits are uncalibrated and often negative for relevant text). `relevance` = the top
  passage's cosine similarity calibrated to 0..1 via `sim_floor`/`sim_target`.
- `router.py` — Groq fast-model classification into safety | maintenance | quality_control | None.
- `agent.py` — the LangGraph graph and `answer_question(question) -> AgentResponse`.
- `judge.py` — LLM-as-judge groundedness (faithfulness) score.
- `guardrails.py` — input (Prompt Guard 2 injection prob, block ≥ threshold) + output
  (gpt-oss-safeguard SAFE/UNSAFE). Both **fail open** (allow + log) on model error.
- `schemas.py` — `AgentResponse.to_dict()`, the /api/chat contract. `confidence_from_score`.
- `settings.py` — all tunables (models, `top_n`/`top_k`, `sim_floor`/`sim_target`,
  `guard_input_threshold`). `require_groq()` fails fast when the agent needs the key.

## Graph (agent.py)
`input_guard → [blocked?] → route → retrieve → [evidence?] → generate → judge → finalize → output_guard → END`
- blocked input short-circuits (skips retrieval/generation).
- no evidence → `gate` node → safe refusal.
- **confidence = retrieval relevance × groundedness**; when < 0.15 the answer is treated as a
  non-answer (citations dropped, domain → unrouted, dangling `[n]` markers stripped).

## Conventions / gotchas
- Generation is grounded ONLY in retrieved context; the system prompt forbids outside knowledge
  and requires inline `[n]` citations. Citations returned to the UI are the deduped retrieved passages.
- The reranker's job is ORDERING and top-k selection, not gating. Gate on similarity.
- Groq free tier is rate-limited — keep LLM calls minimal (route + generate + judge + 2 guards),
  temperature 0. Embeddings/rerank are local by design to keep the hot path off Groq.
- Reranker MUST be small (`ms-marco-MiniLM-L-6-v2`). `bge-reranker-base` is ~100x slower on
  CPU/containers where onnxruntime can't detect the CPU (a first Docker chat took 700s). Startup
  warmup (`Retriever.warm()`) loads models so the first query is fast; models cache in `data/models`.
- `load_backend_settings()` only overrides fields whose env var is set — don't re-hardcode defaults
  there (doing so once silently overrode the dataclass reranker default).
- Add a source: append to `sources.py`, run `ingest --rebuild`, add a retrieval test asserting
  the new doc is returned for a representative query.
