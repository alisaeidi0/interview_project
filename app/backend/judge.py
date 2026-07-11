"""Groundedness judge — LLM-as-judge faithfulness check.

Given the question, the generated answer, and the retrieved context, judges whether
the answer is fully supported by the context (not fabricated). Returns a 0..1 score
that feeds the confidence composite. Advisory, not blocking: a low score lowers
confidence and can trigger the "insufficient evidence" path, but never silently drops
a correct answer.

A custom judge on Groq is used instead of RAGAS to avoid its Ollama-oriented timeout
issues and keep the prototype dependency-light; RAGAS is the productionization path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.backend.llm import chat
from app.backend.settings import BackendSettings

_SYSTEM = (
    "You are a strict faithfulness grader for a retrieval-augmented assistant.\n"
    "Given a QUESTION, an ANSWER, and the retrieved CONTEXT, decide whether every factual "
    "claim in the ANSWER is directly supported by the CONTEXT.\n"
    "Reply with ONLY a JSON object: "
    '{"supported": true|false, "score": 0.0-1.0, "reason": "<one short sentence>"}\n'
    "score = fraction of the answer's claims supported by the context. "
    "If the answer says it lacks evidence, return score 1.0 (correctly refused)."
)


@dataclass
class Groundedness:
    """Result of the faithfulness judgement."""

    supported: bool
    score: float
    reason: str


def judge_groundedness(
    settings: BackendSettings, question: str, answer: str, context: str
) -> Groundedness:
    """Grade whether the answer is supported by the context."""
    user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nCONTEXT:\n{context}"
    raw = chat(
        settings,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        model=settings.groq_judge_model,
        temperature=0.0,
        max_tokens=200,
    )
    return _parse(raw)


def _parse(raw: str) -> Groundedness:
    """Parse the judge's JSON, tolerating code fences or stray text."""
    text = raw.strip()
    if "```" in text:
        text = text.split("```")[1].replace("json", "", 1).strip()
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
        score = float(data.get("score", 0.0))
        return Groundedness(
            supported=bool(data.get("supported", score >= 0.5)),
            score=max(0.0, min(1.0, score)),
            reason=str(data.get("reason", ""))[:200],
        )
    except (ValueError, json.JSONDecodeError):
        # If the judge output is unparseable, fail safe to a neutral-low score.
        return Groundedness(supported=False, score=0.3, reason="judge output unparseable")
