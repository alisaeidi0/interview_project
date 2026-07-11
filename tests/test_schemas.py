"""Tests for the response schema and confidence bucketing.

The /api/chat contract is load-bearing for the frontend, so these assert the exact
shape and the documented confidence thresholds (high >= 0.70, medium >= 0.45).
"""

from __future__ import annotations

from app.backend.schemas import (
    AgentResponse,
    Citation,
    Confidence,
    confidence_from_score,
)


def test_confidence_bucketing_thresholds():
    assert confidence_from_score(0.95).level == "high"
    assert confidence_from_score(0.70).level == "high"      # boundary
    assert confidence_from_score(0.69).level == "medium"
    assert confidence_from_score(0.45).level == "medium"    # boundary
    assert confidence_from_score(0.44).level == "low"
    assert confidence_from_score(0.0).level == "low"


def test_confidence_score_is_clamped():
    assert confidence_from_score(1.5).score == 1.0
    assert confidence_from_score(-0.2).score == 0.0


def test_agent_response_matches_frontend_contract():
    resp = AgentResponse(
        answer="Apply lockout devices to all energy sources.",
        domain="safety",
        confidence=Confidence(level="high", score=0.9),
        citations=[
            Citation(
                source_title="OSHA 3120",
                section="Applying Devices",
                page=12,
                url="https://example.gov/osha3120.pdf",
                snippet="Each device shall be affixed...",
            )
        ],
    )
    d = resp.to_dict()
    # Exact top-level keys the frontend reads.
    assert set(d.keys()) == {"answer", "domain", "confidence", "citations"}
    assert set(d["confidence"].keys()) == {"level", "score"}
    assert set(d["citations"][0].keys()) == {
        "source_title", "section", "page", "url", "snippet"
    }
    assert d["domain"] == "safety"
