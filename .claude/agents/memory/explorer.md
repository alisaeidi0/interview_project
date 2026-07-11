# Explorer memory

Findings and gotchas from past investigations, newest first. A few lines per entry, dated. Not a transcript.

## 2026-07-11 — Backend/LLM stack decision (Manufacturing Floor Assistant)
- Client said "grok"; it means **Groq (GroqCloud)** — hosts open-source models (Llama/Qwen/Gemma) via
  rate-limited API. NOT xAI Grok (proprietary), NOT Ollama. Confirmed by client: has a "grok" key,
  wants open-source models "even if there is a usage limit" → Groq.
- **Groq has NO embeddings API** (inference-only). Decision: embeddings + re-ranking run **local**
  (`bge-small-en-v1.5` + `bge-reranker-base`). Groq only for generation/router/judge/output-guard.
- Groq key was NOT found in env or shell profiles on this machine as of design time — need exact var
  name (likely `GROQ_API_KEY`) before wiring generation.
- Portkey→Claude Sonnet 4.5 kept as a config-swappable option (challenge PDF provides it).

## 2026-07-11 — Data sources (legal status)
- Safety + QC can be fully public-domain: OSHA 3120/3170, 29 CFR 1910.147, NIOSH 2007-131, NIST/SEMATECH
  e-Handbook Ch.6, MIL-STD-1916. US-gov works = public domain (17 USC §105), freely ingestible.
- Maintenance manuals (Goulds/Baldor/Grundfos): free to download, **copyright retained** — client
  approved internal-prototype use only, not redistribution.
- NFPA 70E, ISO 9001, AIAG = paywalled/read-only → cite only, do not ingest.

## 2026-07-11 — Chat UI response contract + visual anatomy (for client one-pager)
- /api/chat response shape (schemas.py AgentResponse.to_dict): {answer:str(markdown), domain:str,
  confidence:{level:"high|medium|low", score:0..1 rounded 2dp}, citations:[{source_title, section,
  page, url, snippet}]}. Same shape from stub.py and real agent — single contract.
- Confidence buckets (schemas.confidence_from_score): score>=0.70 high, >=0.45 medium, else low.
  UI shows "Confidence: {level} · {round(score*100)}%" (chat.js:91). Composite = relevance*groundedness
  (agent finalize_node). Stub example scores: safety 0.91 high, maintenance 0.74 medium, QC 0.88 high,
  fallback 0.21 low.
- Domain labels (chat.js:13): safety→"Safety procedures", maintenance→"Maintenance manuals",
  quality_control→"Quality control", unrouted→"No match". Meta hidden when domain=="unrouted" (chat.js:137).
- Rendered assistant bubble order (chat.js:131-147): [answer-meta: domain badge w/ dot + confidence pill]
  → markdown answer → [Sources block: numbered chips w/ linked title, section·p.N, italic snippet]
  → feedback (👍/👎 "Was this helpful?"). Colors: safety #d97706, maintenance #0891b2, QC #7c3aed,
  unrouted #6b7280; conf high #16a34a/med #d97706/low #dc2626 (styles.css :root).
- Suggested chips (chat.html:33-35): "LOTO steps before servicing", "Pump bearing lubrication interval",
  "Reading a control chart".
- Agent uses REAL retrieval only if GROQ_API_KEY set (main.py:42); else stub. Frontend identical either way.
