# Code-reviewer memory

Recurring issues and project-specific conventions, newest first. A few lines per entry, dated.

## 2026-07-11 — Backend review (agent/retrieval/guardrails) + fixes applied
- Router dropped QC on natural labels ("quality"/"QC"/"quality control" → None because match was
  substring against {"safety","maintenance","quality_control"}). FIXED: router._normalize maps aliases,
  deterministic priority order. Watch for this class of bug wherever an LLM label is matched loosely.
- Input guard failed OPEN on any non-float classifier output (`float(raw)` in broad try/except →
  allow). Adversarial inputs can perturb classifier format, disabling the control. FIXED: distinguish
  error vs unparseable, add regex backstop, don't silently allow. Output guard fail-open documented.
- rerank_floor=-1000 never fires and Passage.rerank_score was dead data; docstring described a
  re-rank gate that doesn't exist. Reconciled docstring + architecture: similarity floor is the gate,
  cross-encoder only orders. If wiring rerank into confidence later, calibrate it (logits are negative).
- Magic 0.15 cite threshold → moved to settings.min_answer_confidence.
- Test integrity was CLEAN: retrieval tests assert the real doc per domain, chunking asserts real
  1910.147; no tautological/self-referential asserts. Keep that bar.

## 2026-07-11 — SQLite create-then-return gotcha
- `create_user` returned None because it read via a NEW connection before the INSERT's connection
  committed (WAL, per-op connections). Pattern: capture lastrowid inside the `with`, fetch AFTER it
  closes. Applies to any create-then-return method in db.py.
