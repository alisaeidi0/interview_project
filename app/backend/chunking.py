"""Sub-section chunking with page tracking and keyword extraction.

Splits a document on its structure (numbered sub-sections / headings) so each chunk
is a coherent unit that maps to a citable location, rather than an arbitrary token
window. Long sections are windowed with overlap; tiny fragments are merged forward.
Page numbers and section headings are carried through for citations, and keywords
(standard/regulation numbers + salient terms) are extracted for hybrid search.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# A line is treated as a heading if it is short and matches one of these shapes.
_HEADING_PATTERNS = [
    re.compile(r"^\d+(?:\.\d+){0,3}\.?\s+[A-Za-z].{0,70}$"),        # "3.2 Applying Locks"
    re.compile(r"^(?:Appendix|Section|Chapter|Part)\s+[A-Z0-9]", re.I),
    re.compile(r"^[A-Z][A-Z0-9 ,/&()\-]{3,60}$"),                    # ALL-CAPS heading
]

# Standard / regulation identifiers, e.g. 1910.147, 29 CFR 1910, 6.3.2.
_ID_PATTERNS = [
    re.compile(r"\b\d{2,4}\.\d{1,4}(?:\([a-z0-9]+\))*\b"),
    re.compile(r"\b\d{1,2}\s?CFR\s?\d+(?:\.\d+)?\b", re.I),
    re.compile(r"\bMIL-STD-\d+\b", re.I),
]

_STOPWORDS = {
    "the", "and", "for", "are", "with", "this", "that", "shall", "from", "you",
    "your", "will", "not", "any", "all", "may", "can", "must", "has", "have",
    "which", "when", "into", "such", "each", "other", "these", "than", "then",
    "there", "their", "been", "also", "who", "was", "were", "our", "out", "use",
    "used", "using", "one", "two", "per", "see", "figure", "table", "page",
}


@dataclass
class Chunk:
    """A citable unit of a document."""

    doc_id: str
    chunk_id: str
    text: str
    section: str
    page: int
    keywords: list[str] = field(default_factory=list)


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not (3 <= len(s) <= 72):
        return False
    if s.endswith((".", ":", ";", ",")) and not re.match(r"^\d", s):
        return False
    return any(p.match(s) for p in _HEADING_PATTERNS)


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    """Pull standard/reg identifiers plus the most frequent salient terms."""
    ids: list[str] = []
    for pat in _ID_PATTERNS:
        ids.extend(m.group(0) for m in pat.finditer(text))

    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())
    freq = Counter(w for w in words if w not in _STOPWORDS)
    common = [w for w, _ in freq.most_common(limit)]

    # De-duplicate while preserving order, ids first.
    seen: set[str] = set()
    out: list[str] = []
    for token in ids + common:
        key = token.lower()
        if key not in seen:
            seen.add(key)
            out.append(token)
    return out[:limit]


def _window(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split an over-long section into overlapping windows at sentence-ish breaks."""
    if len(text) <= max_chars:
        return [text]
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Prefer to break at a paragraph/sentence boundary near the window end.
            cut = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if cut > start + max_chars // 2:
                end = cut + 1
        windows.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [w for w in windows if w]


def chunk_pages(
    doc_id: str,
    pages: list[str],
    max_chars: int = 1400,
    overlap: int = 200,
    min_chars: int = 200,
) -> list[Chunk]:
    """Chunk a document (list of page texts) into citable sub-section chunks."""
    # 1) Flatten to (line, page) and segment into sections by heading.
    sections: list[dict] = []
    current = {"section": "Introduction", "page": 1, "lines": []}

    for page_no, page_text in enumerate(pages, start=1):
        for raw in (page_text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            if _is_heading(line):
                if current["lines"]:
                    sections.append(current)
                current = {"section": line, "page": page_no, "lines": []}
            else:
                current["lines"].append((line, page_no))
    if current["lines"]:
        sections.append(current)

    # 2) Merge tiny sections forward so we don't emit fragments.
    merged: list[dict] = []
    for sec in sections:
        body = " ".join(l for l, _ in sec["lines"])
        if merged and len(body) < min_chars:
            merged[-1]["lines"].extend(sec["lines"])
        else:
            merged.append(sec)

    # 3) Window long sections; emit chunks with page + keywords.
    chunks: list[Chunk] = []
    for sec in merged:
        body = " ".join(l for l, _ in sec["lines"]).strip()
        if not body:
            continue
        start_page = sec["lines"][0][1] if sec["lines"] else sec["page"]
        for i, window in enumerate(_window(body, max_chars, overlap)):
            chunk_id = f"{doc_id}::{len(chunks):04d}"
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    text=window,
                    section=sec["section"][:120],
                    page=start_page,
                    keywords=extract_keywords(window),
                )
            )
    return chunks
