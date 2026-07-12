"""Ingestion pipeline: download -> parse -> chunk -> embed -> store in ChromaDB.

Run as a module:
    python -m app.backend.ingest              # ingest new/updated docs
    python -m app.backend.ingest --rebuild    # wipe the collection and re-ingest

Downloads go to the gitignored data/corpus/. Public-domain docs are safe to store;
copyright-retained manuals are kept locally for the internal prototype only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx
import structlog
from pypdf import PdfReader

from app.backend.chunking import chunk_pages
from app.backend.embeddings import Embedder
from app.backend.settings import BackendSettings, load_backend_settings
from app.backend.sources import SOURCES, Source
from app.backend.vectorstore import VectorStore

log = structlog.get_logger("ingest")


def download(source: Source, corpus_dir: Path) -> Path | None:
    """Download a source PDF if not already present. Returns the path or None."""
    dest = corpus_dir / source.filename
    if dest.exists() and dest.stat().st_size > 0:
        log.info("cached", doc_id=source.doc_id, path=str(dest))
        return dest
    try:
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            resp = client.get(source.url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        dest.write_bytes(resp.content)
        log.info("downloaded", doc_id=source.doc_id, kb=len(resp.content) // 1024)
        return dest
    except (httpx.HTTPError, OSError) as exc:
        log.error("download_failed", doc_id=source.doc_id, url=source.url, error=str(exc))
        return None


def parse_pdf(path: Path) -> list[str]:
    """Extract text per page. Returns a list indexed by page (0 = page 1)."""
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def ingest_source(
    source: Source, settings: BackendSettings, embedder: Embedder, store: VectorStore
) -> int:
    """Download, parse, chunk, embed, and store one source. Returns chunk count."""
    corpus_dir = Path(settings.corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    path = download(source, corpus_dir)
    if path is None:
        return 0

    pages = parse_pdf(path)
    chunks = chunk_pages(
        source.doc_id,
        pages,
        max_chars=settings.max_chunk_chars,
        overlap=settings.chunk_overlap_chars,
    )
    if not chunks:
        log.warning("no_chunks", doc_id=source.doc_id)
        return 0

    embeddings = embedder.embed([c.text for c in chunks])
    metadatas = [
        {
            "doc_id": source.doc_id,
            "title": source.title,
            "domain": source.domain,
            "url": source.url,
            "license": source.license,
            "section": c.section,
            "page": c.page,
            "keywords": ", ".join(c.keywords),
        }
        for c in chunks
    ]
    store.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=metadatas,
    )
    log.info("ingested", doc_id=source.doc_id, domain=source.domain, chunks=len(chunks))
    return len(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest the manufacturing corpus.")
    parser.add_argument("--rebuild", action="store_true", help="wipe collection first")
    args = parser.parse_args(argv)

    settings = load_backend_settings()
    Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
    store = VectorStore(settings.chroma_dir, settings.collection_name)
    if args.rebuild:
        store.reset()
        log.info("collection_reset", name=settings.collection_name)

    embedder = Embedder(settings.embed_model, settings.model_cache_dir)

    total = 0
    by_domain: dict[str, int] = {}
    for source in SOURCES:
        n = ingest_source(source, settings, embedder, store)
        total += n
        by_domain[source.domain] = by_domain.get(source.domain, 0) + n

    log.info("done", total_chunks=total, by_domain=by_domain, stored=store.count())
    if total == 0:
        log.error("nothing_ingested")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
