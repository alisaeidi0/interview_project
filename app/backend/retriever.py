"""Two-stage retrieval: dense search + similarity floor, then cross-encoder re-rank.

Stage 1 pulls a wide candidate set from ChromaDB (optionally domain-filtered) and drops
anything below a cosine-similarity floor. Stage 2 re-scores the survivors with a
cross-encoder and keeps the top-k above a re-rank floor. If nothing survives, the
evidence gate returns empty so the agent can refuse instead of answering weakly.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.backend.embeddings import Embedder, Reranker
from app.backend.settings import BackendSettings
from app.backend.vectorstore import Retrieved, VectorStore


@dataclass
class Passage:
    """A retrieved, re-ranked passage with citation metadata."""

    text: str
    metadata: dict
    similarity: float      # stage-1 cosine similarity (0..1)
    rerank_score: float    # stage-2 cross-encoder logit (higher = more relevant)


@dataclass
class RetrievalResult:
    """Result of a retrieval call."""

    passages: list[Passage]
    relevance: float       # 0..1 calibrated relevance of the best passage

    @property
    def has_evidence(self) -> bool:
        return bool(self.passages)


class Retriever:
    """Owns the embedder, reranker, and vector store for a retrieval session."""

    def __init__(
        self, settings: BackendSettings, store: VectorStore | None = None
    ) -> None:
        self._s = settings
        self._embedder = Embedder(settings.embed_model)
        self._reranker = Reranker(settings.rerank_model)
        self._store = store or VectorStore(settings.chroma_dir, settings.collection_name)

    def retrieve(self, query: str, domain: str | None = None) -> RetrievalResult:
        """Run both retrieval stages and apply the evidence gate."""
        # Stage 1: dense search + similarity floor.
        query_vec = self._embedder.embed_query(query)
        candidates: list[Retrieved] = self._store.query(
            query_vec, n_results=self._s.top_n, domain=domain
        )
        # The similarity floor IS the evidence gate: nothing topical -> refuse.
        survivors = [
            c for c in candidates if (1.0 - c.distance) >= self._s.sim_floor
        ]
        if not survivors:
            return RetrievalResult(passages=[], relevance=0.0)

        # Stage 2: cross-encoder RE-ORDERS the survivors; keep the top-k.
        scores = self._reranker.score(query, [c.text for c in survivors])
        scored = sorted(zip(survivors, scores), key=lambda p: p[1], reverse=True)

        passages: list[Passage] = []
        for cand, score in scored[: self._s.top_k]:
            if score < self._s.rerank_floor:
                continue
            passages.append(
                Passage(
                    text=cand.text,
                    metadata=cand.metadata,
                    similarity=round(1.0 - cand.distance, 4),
                    rerank_score=round(float(score), 4),
                )
            )

        return RetrievalResult(passages=passages, relevance=self._relevance(passages))

    def _relevance(self, passages: list[Passage]) -> float:
        """Calibrate the best passage's cosine similarity to 0..1 confidence input."""
        if not passages:
            return 0.0
        top_sim = max(p.similarity for p in passages)
        span = max(self._s.sim_target - self._s.sim_floor, 1e-6)
        return max(0.0, min(1.0, (top_sim - self._s.sim_floor) / span))
