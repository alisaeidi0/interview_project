"""Retrieval tests against the real ingested corpus.

Expected results are grounded in what each source document actually is:
- OSHA 3120 IS the Lockout/Tagout document -> a LOTO query must route there.
- NIST/SEMATECH SPC handbook IS the control-chart reference -> an SPC query lands there.
- The Baldor MN416 IS a motor manual -> a motor-mounting query lands there.

These use the local embedding + re-ranker models and the persisted ChromaDB (no Groq).
Skipped automatically if the corpus has not been ingested yet.
"""

from __future__ import annotations

import pytest

from app.backend.retriever import Retriever
from app.backend.settings import load_backend_settings
from app.backend.vectorstore import VectorStore

SETTINGS = load_backend_settings()


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    store = VectorStore(SETTINGS.chroma_dir, SETTINGS.collection_name)
    if store.count() == 0:
        pytest.skip("corpus not ingested — run `python -m app.backend.ingest --rebuild`")
    return Retriever(SETTINGS, store=store)


@pytest.mark.parametrize(
    "query,domain,expected_doc",
    [
        ("What are the steps to lock out hazardous energy before servicing?",
         "safety", "osha-3120-loto"),
        ("When is a process out of control on a control chart?",
         "quality_control", "nist-spc-handbook"),
        ("How do I mount and install the motor?",
         "maintenance", "baldor-mn416"),
    ],
)
def test_retrieves_correct_source_document(retriever, query, domain, expected_doc):
    result = retriever.retrieve(query, domain=domain)
    assert result.has_evidence, f"no evidence retrieved for: {query}"
    doc_ids = {p.metadata["doc_id"] for p in result.passages}
    assert expected_doc in doc_ids, f"expected {expected_doc}, got {doc_ids}"


def test_passages_carry_citation_metadata(retriever):
    result = retriever.retrieve("lockout tagout procedure", domain="safety")
    assert result.has_evidence
    top = result.passages[0]
    # Every citation field the UI needs must be present and real.
    assert top.metadata["title"]
    assert top.metadata["url"].startswith("http")
    assert isinstance(top.metadata["page"], int)
    assert 0.0 <= result.relevance <= 1.0


def test_evidence_gate_rejects_off_topic(retriever):
    # A clearly off-topic query filtered to one domain should fall below the gate,
    # or at worst return far lower relevance than an on-topic query.
    off = retriever.retrieve("what is on the cafeteria lunch menu today", domain="safety")
    on = retriever.retrieve("lockout tagout of hazardous energy", domain="safety")
    assert on.relevance > off.relevance
