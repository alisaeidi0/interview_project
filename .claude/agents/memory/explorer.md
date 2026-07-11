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
