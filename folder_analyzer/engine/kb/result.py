"""KBResult — the Knowledge Base's single output value (Phase 4).

A KBResult is a *classification* verdict only: the resolved category, the tier
that matched, and a confidence hint — plus provenance (``detail``) that Phase 5
will turn into recommendation `reason_key` / `reason_params`.

Deliberate boundary: a KBResult never carries or constructs an ``Assessment``.
Safety judgments (invariants I1-I10) are assembled in Phase 5 from these
verdicts; the KB layer alone can never label something SAFE_TO_DELETE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_VALID_CONFIDENCE = ("high", "medium", "low")


@dataclass(frozen=True)
class KBResult:
    """Classification of a single path by the tiered knowledge base.

    Attributes:
        path: the normalized classified path.
        category: stable category string; ``"unknown"`` when no tier matched.
        tier: matched tier, 0..5; ``None`` when nothing matched (path-level
            dispatch) or when the verdict came from content analysis.
        confidence_hint: ``"high"`` | ``"medium"`` | ``"low"`` — coarse hint;
            real confidence numbers are Phase 5 work.
        level: analysis level that produced the verdict — ``1`` (path/metadata
            only), ``2`` (magic bytes <=512 B) or ``3`` (targeted <=4 KB).
        detail: provenance, e.g. the matched rule or signature, for reason
            keys and forensic traceability.
    """

    path: str
    category: str = "unknown"
    tier: Optional[int] = None
    confidence_hint: str = "low"
    level: int = 1
    detail: str = ""

    def __post_init__(self) -> None:
        if self.confidence_hint not in _VALID_CONFIDENCE:
            raise ValueError(
                f"invalid confidence_hint: {self.confidence_hint!r}"
            )
        if self.tier is not None and not (0 <= self.tier <= 5):
            raise ValueError(f"invalid tier: {self.tier!r}")
        if self.level not in (1, 2, 3):
            raise ValueError(f"invalid analysis level: {self.level!r}")