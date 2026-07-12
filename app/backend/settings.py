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
    # ms-marco-MiniLM is a small, fast cross-encoder — near-instant inference even on
    # CPU/containers where onnxruntime can't detect the CPU and uses generic kernels
    # (bge-reranker-base was ~100x slower there). Quality is fine for domain re-ranking.
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"

    # Storage paths (under gitignored data/).
    chroma_dir: str = str(REPO_ROOT / "data" / "chroma")
    corpus_dir: str = str(REPO_ROOT / "data" / "corpus")
    # Local model cache — under data/ so it persists in the Docker volume across restarts.
    model_cache_dir: str = str(REPO_ROOT / "data" / "models")
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
    # Below this composite confidence, an answer is treated as a non-answer: citations
    # are dropped and it is stamped unrouted (avoids parading sources on a weak/refused reply).
    min_answer_confidence: float = 0.15

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
    """Build BackendSettings from the environment.

    Only overrides fields whose env var is actually set, so the dataclass defaults
    above remain the single source of truth (avoids the defaults drifting between the
    dataclass and this loader).
    """
    overrides: dict[str, str] = {}
    for field_name, env_var in (
        ("groq_model", "GROQ_MODEL"),
        ("groq_judge_model", "GROQ_JUDGE_MODEL"),
        ("embed_model", "EMBED_MODEL"),
        ("rerank_model", "RERANK_MODEL"),
    ):
        value = os.environ.get(env_var)
        if value:
            overrides[field_name] = value
    return BackendSettings(groq_api_key=os.environ.get("GROQ_API_KEY"), **overrides)
