"""Question router: classify a question into a documentation domain.

Uses the fast Groq model at temperature 0. Returns one of the three domains, or None
when the model can't confidently place it (the agent then searches across domains and
leans on the evidence gate instead of forcing a wrong route).
"""

from __future__ import annotations

from app.backend.llm import chat
from app.backend.settings import BackendSettings
from app.backend.sources import MAINTENANCE, QUALITY, SAFETY

_SYSTEM = (
    "You route plant-floor questions to exactly one documentation domain.\n"
    "Domains:\n"
    "- safety: lockout/tagout, hazardous energy, machine guarding, PPE, confined space, injury prevention.\n"
    "- maintenance: installing, servicing, lubricating, aligning, or repairing equipment "
    "(motors, pumps, bearings, gearboxes).\n"
    "- quality_control: SPC, control charts, sampling, inspection, tolerances, defects, capability (Cpk).\n"
    "Reply with ONLY the domain label: safety, maintenance, or quality_control. "
    "If it clearly fits none, reply: none."
)


def route(settings: BackendSettings, question: str) -> str | None:
    """Return the routed domain, or None if unclear/out-of-scope."""
    label = chat(
        settings,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": question},
        ],
        model=settings.groq_judge_model,
        temperature=0.0,
        max_tokens=8,
    ).lower().strip().strip(".")

    return _normalize(label)


def _normalize(label: str) -> str | None:
    """Map the model's label to a domain, tolerating shortened forms.

    Checked in priority order so a deterministic result is returned even if the label
    contains more than one keyword. 'quality_control' is the label most likely to be
    emitted in a short form ('quality', 'qc'), so it needs explicit aliases.
    """
    if "maintenance" in label:
        return MAINTENANCE
    if "safety" in label:
        return SAFETY
    if "quality" in label or "quality_control" in label or label == "qc" or "qc " in label:
        return QUALITY
    return None
