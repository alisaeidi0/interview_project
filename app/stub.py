"""Stub answer engine for frontend experimentation.

Returns realistic, correctly-shaped responses so the UI (routing badge, citations,
confidence) can be exercised before the real LangGraph agent exists. The response
schema here is the contract the real backend will fulfill, so the frontend needs no
changes when we wire in the agent.

NOTE: These answers are canned demo content, NOT retrieved from real documents. The
real backend replaces this module. Citations point at the actual public-domain source
documents so the format is representative.
"""

from __future__ import annotations

from typing import Any

# Keyword hints → domain, mirroring what the real router will classify.
_ROUTING_HINTS: dict[str, list[str]] = {
    "safety": ["lockout", "lock out", "tagout", "tag out", "loto", "hazard", "ppe",
               "guard", "arc flash", "energy", "1910.147", "injury", "confined space",
               "ergonomic", "servic", "before servic", "de-energize"],
    "maintenance": ["pump", "motor", "bearing", "lubricat", "seal", "vibration",
                    "align", "grease", "impeller", "gearbox", "compressor", "repair"],
    "quality_control": ["spc", "control chart", "x-bar", "x̄", "sampling", "defect",
                        "tolerance", "inspection", "cpk", "six sigma", "acceptance",
                        "iso 9001", "measurement", "calibration", "out of control"],
}

_CANNED: dict[str, dict[str, Any]] = {
    "safety": {
        "answer": (
            "**Before servicing the equipment, apply lockout/tagout (LOTO):**\n\n"
            "1. Notify affected employees that servicing is required.\n"
            "2. Shut down the machine using its normal stopping procedure.\n"
            "3. Isolate every energy source (electrical, hydraulic, pneumatic, stored energy).\n"
            "4. Apply your assigned lock and tag to each isolation point.\n"
            "5. Release or restrain stored energy (springs, capacitors, elevated parts).\n"
            "6. **Verify zero energy state** by attempting a normal start, then return controls to off.\n\n"
            "Only the employee who applied a lock may remove it."
        ),
        "domain": "safety",
        "confidence": {"level": "high", "score": 0.91},
        "citations": [
            {"source_title": "OSHA 3120 — Control of Hazardous Energy (Lockout/Tagout)",
             "section": "Applying Lockout/Tagout Devices", "page": 12,
             "url": "https://www.osha.gov/sites/default/files/publications/OSHA3120.pdf",
             "snippet": "Each lockout or tagout device shall be affixed to each energy-isolating device..."},
            {"source_title": "29 CFR 1910.147", "section": "(d) Application of control", "page": None,
             "url": "https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147",
             "snippet": "The established procedures for the application of energy control..."},
        ],
    },
    "maintenance": {
        "answer": (
            "**Recommended lubrication interval for the pump bearings:**\n\n"
            "Under normal operating conditions, re-grease anti-friction bearings every "
            "**2,000 operating hours** (roughly quarterly for continuous duty). Use an "
            "NLGI Grade 2 lithium-based grease unless the nameplate specifies otherwise.\n\n"
            "Watch for early warning signs between intervals: rising bearing-housing "
            "temperature, increased vibration, or audible noise — any of these warrants "
            "inspection ahead of the scheduled interval."
        ),
        "domain": "maintenance",
        "confidence": {"level": "medium", "score": 0.74},
        "citations": [
            {"source_title": "Goulds 3296-S — Installation, Operation & Maintenance",
             "section": "Preventive Maintenance — Lubrication", "page": 34,
             "url": "https://www.gouldspumps.com/getmedia/ca7a636d-4d1c-4e03-95f4-399d450406cf/IOM_3296-S.pdf",
             "snippet": "Regrease bearings every 2000 hours of operation with a good grade of..."},
        ],
    },
    "quality_control": {
        "answer": (
            "**Interpreting the X̄ control chart for an out-of-control signal:**\n\n"
            "The process is signaled out of control when any of these occur:\n\n"
            "- A single point falls beyond the ±3σ control limits.\n"
            "- Two of three consecutive points fall beyond ±2σ on the same side.\n"
            "- Eight consecutive points fall on the same side of the centerline.\n\n"
            "When a rule triggers, stop and investigate the assignable cause before "
            "continuing production — do not adjust the process based on common-cause variation."
        ),
        "domain": "quality_control",
        "confidence": {"level": "high", "score": 0.88},
        "citations": [
            {"source_title": "NIST/SEMATECH e-Handbook of Statistical Methods",
             "section": "6.3.2 What are Control Charts?", "page": None,
             "url": "https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm",
             "snippet": "A process is out of control if a point falls outside the control limits..."},
        ],
    },
}

_FALLBACK: dict[str, Any] = {
    "answer": (
        "I don't have confident evidence in the current documentation to answer that. "
        "Try rephrasing, or ask about lockout/tagout and safety procedures, equipment "
        "maintenance, or quality-control standards."
    ),
    "domain": "unrouted",
    "confidence": {"level": "low", "score": 0.21},
    "citations": [],
}


def route(question: str) -> str:
    """Pick a domain from keyword hints (stand-in for the real LLM router)."""
    q = question.lower()
    best_domain, best_hits = "unrouted", 0
    for domain, hints in _ROUTING_HINTS.items():
        hits = sum(1 for h in hints if h in q)
        if hits > best_hits:
            best_domain, best_hits = domain, hits
    return best_domain


def answer(question: str) -> dict[str, Any]:
    """Return a canned, correctly-shaped response for the routed domain."""
    domain = route(question)
    if domain == "unrouted":
        return dict(_FALLBACK)
    return dict(_CANNED[domain])
