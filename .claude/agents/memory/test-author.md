# Test-author memory

Testing conventions, fixture locations, how to run the suite, and gotchas, newest first. A few lines per entry, dated.

## 2026-07-11 — Test suite established
- Run: `set -a; . ./.env; set +a; .venv/bin/python -m pytest tests/ -v` (env load gives GROQ_API_KEY).
- 15 tests, all passing. Structure: test_chunking + test_schemas (no API), test_retrieval (local
  models + ChromaDB, skips if corpus empty), test_agent_integration (Groq, skips if no key).
- Expected-value sources used: OSHA 3120 IS the LOTO doc, NIST/SEMATECH IS the SPC handbook, Baldor
  MN416 IS the motor manual → retrieval tests assert the right doc_id per domain. `1910.147` is the
  real OSHA LOTO reg number → keyword test asserts it's extracted. Confidence thresholds from
  schemas.confidence_from_score (high>=0.70, medium>=0.45).
- Gotcha: tests that need Groq or the corpus must `pytest.skip`/`skipif`, so the offline unit suite
  still runs. Don't hard-fail on missing key/DB.
- Gotcha: chromadb emits harmless telemetry errors + a pydantic model_fields deprecation warning —
  ignore; filter test output with `grep -vE "telemetry|Deprecation|Fetching|it/s"`.
- Corpus must be ingested first (`python -m app.backend.ingest --rebuild`) or retrieval tests skip.
