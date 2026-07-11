"""Guardrails: input injection/jailbreak detection and output safety classification.

Both run on Groq-hosted, purpose-built safety models:
- Input: Llama Prompt Guard 2 returns a 0..1 probability that the text is a
  prompt-injection / jailbreak attempt; we block above a threshold.
- Output: gpt-oss-safeguard classifies the generated answer as SAFE / UNSAFE against
  a workplace-assistant policy.

Guards fail OPEN (allow, with a logged warning) if the model errors, so a transient
guard failure degrades to normal answering rather than blocking legitimate questions.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.backend.llm import chat
from app.backend.settings import BackendSettings

log = structlog.get_logger("guardrails")

_OUTPUT_POLICY = (
    "You are a content-safety classifier for a workplace manufacturing documentation "
    "assistant. An answer is UNSAFE only if it contains content that could cause harm: "
    "instructions for weapons/explosives, illegal activity, self-harm, hate, or other "
    "clearly dangerous content. Grounded safety/maintenance/quality guidance is SAFE. "
    "Reply with exactly one word: SAFE or UNSAFE."
)


@dataclass
class InputVerdict:
    """Result of the input guardrail."""

    blocked: bool
    injection_score: float


def check_input(settings: BackendSettings, text: str) -> InputVerdict:
    """Classify a user message for prompt injection / jailbreak."""
    try:
        raw = chat(
            settings,
            messages=[{"role": "user", "content": text}],
            model=settings.groq_guard_input_model,
            temperature=0.0,
            max_tokens=8,
        )
        score = float(raw.strip())
    except Exception as exc:  # noqa: BLE001 - fail open (allow) on guard failure, but log
        log.warning("input_guard_error", error=str(exc)[:200])
        return InputVerdict(blocked=False, injection_score=0.0)

    blocked = score >= settings.guard_input_threshold
    if blocked:
        log.warning("input_blocked", injection_score=round(score, 4))
    return InputVerdict(blocked=blocked, injection_score=score)


def check_output(settings: BackendSettings, answer: str) -> bool:
    """Return True if the answer is safe to show, False if it should be withheld."""
    try:
        verdict = chat(
            settings,
            messages=[
                {"role": "system", "content": _OUTPUT_POLICY},
                {"role": "user", "content": answer},
            ],
            model=settings.groq_guard_output_model,
            temperature=0.0,
            max_tokens=8,
        )
    except Exception as exc:  # noqa: BLE001 - fail open, but log
        log.warning("output_guard_error", error=str(exc)[:200])
        return True

    safe = "unsafe" not in verdict.strip().lower()
    if not safe:
        log.warning("output_blocked")
    return safe
