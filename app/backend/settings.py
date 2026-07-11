"""Backend configuration (retrieval + agent), resolved from the environment.

Separate from the frontend `app.config` so ingestion can run without the web
app's auth settings, and vice versa. Groq settings are required only when the
agent actually runs (see `require_groq`), so local ingestion works offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when required backend configuration is missing."""


@dataclass(frozen=True)
class BackendSettings:
    """Immutable backend settings."""

    # Groq models (see `groq /models` — all confirmed available on the project key).
    groq_api_key: str | None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_judge_model: str = "llama-3.1-8b-instant"
    groq_guard_input_model: str = "meta-llama/llama-prompt-guard-2-86m"
    groq_guard_output_model: str = "openai/gpt-oss-safeguard-20b"

    # Local retrieval models (no API, no rate limit).
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "BAAI/bge-reranker-base"

    # Storage paths (under gitignored data/).
    chroma_dir: str = str(REPO_ROOT / "data" / "chroma")
    corpus_dir: str = str(REPO_ROOT / "data" / "corpus")
    collection_name: str = "manufacturing_docs"

    # Retrieval parameters.
    top_n: int = 20            # candidates pulled by vector search
    top_k: int = 4             # kept after cross-encoder re-rank
    sim_floor: float = 0.30    # min cosine similarity to survive stage 1 (the evidence gate)
    sim_target: float = 0.72   # cosine similarity mapped to relevance 1.0 (bge-small calibration)
    # The cross-encoder ORDERS survivors; it is not a hard zero-threshold gate, because
    # bge-reranker logits are uncalibrated (often negative for relevant passages).
    rerank_floor: float = -1000.0

    # Generation.
    temperature: float = 0.0
    max_chunk_chars: int = 1400
    chunk_overlap_chars: int = 200

    # Guardrails.
    guard_input_threshold: float = 0.5  # Prompt Guard 2 injection probability to block

    def require_groq(self) -> str:
        """Return the Groq key or fail fast — call this before invoking the agent."""
        if not self.groq_api_key:
            raise ConfigError(
                "Missing GROQ_API_KEY. Set it in .env (see .env.example). "
                "The agent needs it to reach Groq-hosted models."
            )
        return self.groq_api_key


def load_backend_settings() -> BackendSettings:
    """Build BackendSettings from the environment (with sensible defaults)."""
    def _get(name: str, default: str) -> str:
        return os.environ.get(name, default)

    return BackendSettings(
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        groq_model=_get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_judge_model=_get("GROQ_JUDGE_MODEL", "llama-3.1-8b-instant"),
        embed_model=_get("EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        rerank_model=_get("RERANK_MODEL", "BAAI/bge-reranker-base"),
    )
