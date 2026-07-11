"""Groq client helpers. All generation runs here at temperature 0 for determinism.

Uses the Groq SDK directly (OpenAI-compatible) rather than a heavier framework wrapper,
so the varied model types — chat, prompt-guard classifier, safeguard — share one client.
"""

from __future__ import annotations

from functools import lru_cache

from groq import Groq

from app.backend.settings import BackendSettings


@lru_cache(maxsize=1)
def get_client(api_key: str) -> Groq:
    """Cached Groq client (keyed by api_key so tests can vary it)."""
    return Groq(api_key=api_key)


def chat(
    settings: BackendSettings,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 1024,
) -> str:
    """Single chat completion; returns the assistant message text."""
    client = get_client(settings.require_groq())
    resp = client.chat.completions.create(
        model=model or settings.groq_model,
        messages=messages,
        temperature=settings.temperature if temperature is None else temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()
