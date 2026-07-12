"""ChromaDB wrapper — a single persistent collection with per-domain metadata.

The design names three logical collections (safety / maintenance / QC); we implement
them as one physical collection filtered by a `domain` metadata field. Same routing
outcome, less duplication, and it allows a cross-domain search when routing is unsure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb


@dataclass
class Retrieved:
    """One retrieved chunk with its citation metadata and vector distance."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float


class VectorStore:
    """Thin wrapper over a persistent Chroma collection using cosine space."""

    def __init__(self, persist_dir: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def reset(self) -> None:
        """Drop and recreate the collection (used by `ingest --rebuild`)."""
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert a batch of chunks."""
        self._collection.add(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def count(self) -> int:
        """Number of stored chunks."""
        return self._collection.count()

    def query(
        self,
        query_embedding: list[float],
        n_results: int,
        domain: str | None = None,
    ) -> list[Retrieved]:
        """Vector search, optionally filtered to a single domain."""
        where = {"domain": domain} if domain else None
        res = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [
            Retrieved(chunk_id=i, text=d, metadata=m, distance=dist)
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]
