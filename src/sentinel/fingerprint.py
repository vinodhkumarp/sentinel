"""Turning many findings into few incidents.

The whole value of this module is negative: it is what stops Sentinel telling
you about the same broken bank forty times. Two findings belong to one incident
when their class, scope and *normalised* error text agree -- normalised because
otherwise "product a3f2... failed" and "product 9c41... failed" look like
different problems when they are plainly the same one.
"""

from __future__ import annotations

import hashlib
import re

from .model import Finding

# Order matters: UUIDs before the generic hex rule, which would otherwise eat
# their leading segment and leave punctuation behind.
_SUBSTITUTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
        "<uuid>",
    ),
    (
        re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"),
        "<ts>",
    ),
    (re.compile(r"\b[0-9a-f]{8,}\b", re.I), "<hex>"),
    # Four digits or more. Three-digit numbers are left alone on purpose: an
    # HTTP status is part of what the error IS, not an incidental identifier.
    (re.compile(r"\b\d{4,}\b"), "<n>"),
    (re.compile(r"\s+"), " "),
)


def normalise_error(text: str | None) -> str:
    """Strip the parts of an error message that differ between identical failures."""
    if not text:
        return ""
    normalised = text.strip()
    for pattern, replacement in _SUBSTITUTIONS:
        normalised = pattern.sub(replacement, normalised)
    return normalised.strip().lower()[:500]


def fingerprint(finding: Finding) -> str:
    """A stable id for "this same problem", across runs.

    Truncated to 16 hex characters: short enough to paste into a message,
    far more than enough to keep a few thousand incidents apart.
    """
    material = "\x1f".join(
        (finding.failure_class.value, finding.scope, normalise_error(finding.signature))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
