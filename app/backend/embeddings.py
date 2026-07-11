"""Local embedding and cross-encoder re-ranking via fastembed (ONNX, no GPU/torch).

Both models run in-process with no external API, so the retrieval hot path is free
and unthrottled — deliberately kept off Groq, which has no embeddings API anyway.
Models are loaded lazily and cached so the (slow) first load happens once.
"""

from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder


@lru_cache(maxsize=2)
def _embedder(model_name: str) -> TextEmbedding:
    return TextEmbedding(model_name=model_name)


@lru_cache(maxsize=2)
def _reranker(model_name: str) -> TextCrossEncoder:
    return TextCrossEncoder(model_name=model_name)


class Embedder:
    """Dense embeddings for documents and queries."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into plain float lists (Chroma-ready)."""
        vectors = _embedder(self._model_name).embed(texts)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        return self.embed([text])[0]


class Reranker:
    """Cross-encoder relevance scoring for query/document pairs."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Return one relevance score per document (higher = more relevant)."""
        if not documents:
            return []
        return list(_reranker(self._model_name).rerank(query, documents))
