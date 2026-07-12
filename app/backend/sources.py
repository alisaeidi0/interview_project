"""Catalog of source documents for the corpus.

Every entry is a real, verifiable document. US-government works (OSHA, NIOSH, NIST,
MIL-STD) are public domain (17 U.S.C. Sec. 105) and freely ingestible. Manufacturer
manuals are free to download but copyright-retained — flagged internal-only.

Licensing is tracked per source so we never silently redistribute restricted material.
"""

from __future__ import annotations

from dataclasses import dataclass

# Routing domains — must match the frontend badge keys.
SAFETY = "safety"
MAINTENANCE = "maintenance"
QUALITY = "quality_control"

PUBLIC_DOMAIN = "public-domain-us-gov"
COPYRIGHT_INTERNAL = "copyright-retained-internal-only"


@dataclass(frozen=True)
class Source:
    """A single ingestible document."""

    doc_id: str
    title: str
    domain: str
    url: str
    license: str
    filename: str


# Focused, all-domain corpus. Each URL was confirmed reachable during research.
SOURCES: list[Source] = [
    Source(
        doc_id="osha-3120-loto",
        title="OSHA 3120 — Control of Hazardous Energy (Lockout/Tagout)",
        domain=SAFETY,
        url="https://www.osha.gov/sites/default/files/publications/OSHA3120.pdf",
        license=PUBLIC_DOMAIN,
        filename="osha-3120-loto.pdf",
    ),
    Source(
        doc_id="osha-3170-machine-guarding",
        title="OSHA 3170 — Safeguarding Equipment and Protecting Employees from Amputations",
        domain=SAFETY,
        url="https://www.osha.gov/sites/default/files/publications/OSHA3170.pdf",
        license=PUBLIC_DOMAIN,
        filename="osha-3170-machine-guarding.pdf",
    ),
    Source(
        doc_id="nist-spc-handbook",
        title="NIST/SEMATECH e-Handbook — Process or Product Monitoring and Control (SPC)",
        domain=QUALITY,
        url="https://www.itl.nist.gov/div898/handbook/toolaids/pff/pmc.pdf",
        license=PUBLIC_DOMAIN,
        filename="nist-spc-handbook.pdf",
    ),
    Source(
        # Manufacturer manual: free to download, copyright retained -> internal prototype only.
        doc_id="baldor-mn416",
        title="Baldor-Reliance MN416 — AC & DC Motor Installation & Maintenance",
        domain=MAINTENANCE,
        url="https://www.baldor.com/mvc/downloadcenter/files/mn416",
        license=COPYRIGHT_INTERNAL,
        filename="baldor-mn416.pdf",
    ),
]
