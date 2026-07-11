# CLAUDE.md

Standing rules for this project. Loaded every session — keep it lean.

## Engineering standards
- Clear naming, type hints, docstrings on public functions/classes.
- Small, single-purpose functions. No dead code (delete, don't comment out).
- No hardcoded secrets or config — use environment variables. Fail fast and clearly on missing config.
- Handle errors explicitly. Only validate at system boundaries (user input, external APIs); trust internal code.

## Definition of done
A feature is done when it (1) runs, (2) has at least one test proving it works against a real, verifiable expected result — never an invented one, and (3) fails cleanly on bad input/config.

## Git discipline
- Atomic commits: one logical reason each. If the message needs "and", split it. Every commit leaves the project working.
- Conventional Commits: `type(scope): description`, imperative mood (feat, fix, refactor, docs, test, chore, perf). Body explains *why* when non-obvious.
- Commit at each meaningful checkpoint so history tells the build's story. Use a branch for a distinct feature when it makes sense.
- Before committing: show staged diff + proposed message, wait for go-ahead. Never commit secrets, large data files, or half-broken code.

## Delegation & context discipline (subagents)
- All research, codebase exploration, log reading, multi-file analysis, or open-ended investigation happens in a subagent, never the main thread. Subagents return a concise summary + concrete recommendation, not raw dumps.
- Run independent subagent tasks in parallel when they don't depend on each other.
- Main session is the coordinator: holds the plan, dispatches work, integrates results.
- When dispatching, state in one line what's being delegated and why.
- Project subagents (`.claude/agents/`): `explorer` (read-only investigation), `code-reviewer` (quality/security/test-integrity review, no edits), `test-author` (writes tests against verified expected results). Each maintains notes in `.claude/agents/memory/<agent>.md` — read at start, update at end.
- Research must be grounded: cite real sources (files, data, official docs). State findings separately from inference. Surface disagreement/uncertainty rather than picking an answer silently. Prefer primary sources; flag single-source claims.

## Checkpoints — pause and ask before
- Committing to an architecture, major library/framework, or overall approach.
- Choosing between materially different design directions, or reversing a prior decision.
- Anything hard/expensive to undo: schemas/data models, deleting or overwriting substantial work, destructive git ops, broad system/env changes.
- Anything that changes scope, plan, or definition of done.
- A research conclusion that will drive the build — surface the finding + a recommendation, don't act on it silently.
- Genuine uncertainty, blockage, or ambiguous requirements.

Don't pause for: naming/formatting, small refactors, code following an already-agreed approach, installing already-planned dependencies, running tests, routine bug fixes, or progress through an approved plan — just do it and narrate.

When a checkpoint hits: state it in 1-2 lines, give realistic options with a one-line tradeoff each, give a recommendation, then wait.

## Knowledge capture
At the end of every meaningful task, before moving on:
- Record findings, decisions (+why), gotchas, and lessons into the relevant subagent's memory file and/or a repo notes file.
- Turn repeatable patterns into a new/updated skill (`.claude/skills/`) instead of letting them evaporate.
- Update the Project Map below if structure changed.
- Target: a fresh session reading only this file + skills can pick up without re-explanation.

## Visuals
- Mermaid for architecture/flow/sequence/state diagrams, committed as text, kept in sync with the real design.
- Real charts (saved image or rendered view) for any data/results worth seeing — never just describe numbers that could be charted.

## Build defaults
- Plan briefly before non-trivial work, get checkpoint sign-off, then implement the simplest design that meets the need.
- Work in vertical slices — one thin end-to-end path before widening.
- Verify as you go: run/test after each change and show real output, not a claim of success.
- Tests assert against real expected results from a trustworthy source — state the source.
- Config/secrets via environment variables from the start.
- Run long commands in the background where possible; keep working on the next piece.

## Project map
Building the **Manufacturing Floor Assistant** — agentic RAG chatbot routing floor-supervisor
questions to Safety / Maintenance / QC docs with grounded, cited, confidence-scored answers.
Full design in [docs/architecture.md](docs/architecture.md) (approved 2026-07-11).

Stack: FastAPI + HTML/CSS/JS frontend · LangGraph agent · Groq open-source LLM (temp=0) ·
local embeddings + cross-encoder re-rank (`bge-small` / `bge-reranker`) · ChromaDB · Redis ·
Postgres · guardrails (Prompt Guard 2, LLM Guard, RAGAS faithfulness, Llama Guard 3) ·
Langfuse + structlog · Docker Compose. Build order: **frontend → backend → wiring**.

- `docs/architecture.md` — approved architecture, stack rationale, diagrams, data sources
- `.claude/agents/` — subagent definitions: `explorer`, `code-reviewer`, `test-author`
- `.claude/agents/memory/` — persistent per-agent notes, updated after each task
- `.claude/skills/` — reusable playbooks, added as repeatable patterns emerge

_(Update this section as real structure — languages, services, entry points — takes shape.)_
