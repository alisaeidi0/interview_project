"""Response schema shared by the agent and the /api/chat endpoint.

This is the single source of truth for the contract the frontend consumes. The stub
(`app.stub`) and the real agent both produce this shape, so the UI never changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Citation:
    """A pointer to the exact source location an answer used."""

    source_title: str
    section: str | None = None
    page: int | None = None
    url: str | None = None
    snippet: str | None = None


@dataclass
class Confidence:
    """Displayed confidence: a level bucket plus the raw composite score."""

    level: str   # high | medium | low
    score: float # 0..1


@dataclass
class AgentResponse:
    """The full answer payload returned to the frontend."""

    answer: str
    domain: str
    confidence: Confidence
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def confidence_from_score(score: float) -> Confidence:
    """Bucket a 0..1 composite score into high/medium/low."""
    score = max(0.0, min(1.0, score))
    if score >= 0.70:
        level = "high"
    elif score >= 0.45:
        level = "medium"
    else:
        level = "low"
    return Confidence(level=level, score=round(score, 2))
