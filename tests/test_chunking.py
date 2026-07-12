"""Tests for sub-section chunking and keyword extraction.

Expected values are derived from the documented behavior of the chunker and from
real regulatory identifiers (e.g. 29 CFR 1910.147, the actual OSHA LOTO citation),
not from whatever the implementation happens to output.
"""

from __future__ import annotations

from app.backend.chunking import chunk_pages, extract_keywords


def test_extract_keywords_finds_regulation_identifiers():
    # 1910.147 is the real OSHA Lockout/Tagout standard number — a known fact.
    text = "The employer shall comply with 29 CFR 1910.147 for lockout and tagout."
    keywords = extract_keywords(text)
    assert "1910.147" in keywords
    assert any("CFR" in k for k in keywords)
    assert "lockout" in keywords


def test_extract_keywords_deduplicates_and_limits():
    text = "bearing bearing bearing motor motor lubrication " * 5
    keywords = extract_keywords(text, limit=5)
    assert len(keywords) <= 5
    assert len(keywords) == len(set(k.lower() for k in keywords))


def test_chunk_pages_splits_on_headings_and_tracks_pages():
    pages = [
        "1. INTRODUCTION\nThis section introduces the safety program overview.",
        "2. LOCKOUT PROCEDURE\nApply a lock to each energy-isolating device before service.",
    ]
    chunks = chunk_pages("doc", pages, max_chars=1400, overlap=200, min_chars=10)

    assert chunks, "expected at least one chunk"
    # Page numbers are 1-indexed and real.
    assert all(c.page in (1, 2) for c in chunks)
    # The heading-based section is captured for citation.
    assert any("LOCKOUT" in c.section.upper() for c in chunks)
    # Chunk ids are unique and namespaced to the doc.
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(cid.startswith("doc::") for cid in ids)


def test_chunk_pages_windows_long_sections():
    long_body = "Sentence about torque values. " * 200  # ~6000 chars, one section
    pages = [f"3. MAINTENANCE\n{long_body}"]
    chunks = chunk_pages("doc", pages, max_chars=1400, overlap=200, min_chars=10)

    # A ~6000-char section must be split into multiple ~1400-char windows.
    assert len(chunks) >= 3
    assert all(len(c.text) <= 1500 for c in chunks)
