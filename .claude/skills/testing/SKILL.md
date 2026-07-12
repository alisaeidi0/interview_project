---
name: testing
description: How tests are structured and run in this project, and the rule that expected values must come from a trustworthy source. Use when adding or running tests.
---

# Testing

`pytest`, tests under `tests/`. Run the suite:

```bash
set -a; . ./.env; set +a          # load env (GROQ_API_KEY etc.)
.venv/bin/python -m pytest tests/ -v
```

## The rule
Every assertion checks a **real expected value from a trustworthy source** — never a value copied
from the implementation's current output. State the source in a comment.

## What's covered
- `test_chunking.py` — keyword extraction (asserts the real OSHA number `1910.147` is found),
  sub-section splitting, page tracking, long-section windowing. **No API.**
- `test_schemas.py` — confidence buckets (high ≥ 0.70, medium ≥ 0.45) and the exact `/api/chat`
  response shape the frontend consumes. **No API.**
- `test_retrieval.py` — asserts the correct **real document** is retrieved per domain (LOTO query →
  OSHA 3120, SPC query → NIST handbook, motor query → Baldor manual), citation metadata is present,
  and the evidence gate ranks off-topic below on-topic. Uses local models + persisted ChromaDB;
  **skips if the corpus isn't ingested.**
- `test_agent_integration.py` — full agent: safety question answered + OSHA-cited, prompt injection
  blocked, off-topic refused without citations. **Skips if `GROQ_API_KEY` is unset.**

## Conventions
- Tests that need Groq or the corpus **skip cleanly** (via `pytest.skip` / `skipif`) so the offline
  unit suite always runs — don't make them hard-fail on a missing key/DB.
- One behavior per test; name the test after the behavior it proves.
- When adding a corpus source or changing retrieval, add/adjust a `test_retrieval.py` case that
  asserts the expected real document is returned.
