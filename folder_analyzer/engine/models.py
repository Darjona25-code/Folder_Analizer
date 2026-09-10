"""Safety-model value objects and the construction-time confidence gate (Phase 2).

The confidence gate (I9) is enforced *at construction*: an ``Assessment`` with
``recommendation == SAFE_TO_DELETE`` and ``confidence != HIGH`` is structurally
unrepresentable because ``__post_init__`` promotes it to ``REVIEW_FIRST``.
The same gate is exposed as a pure function for tests and the Phase 5 engine.

I3 (UNKNOWN impact) and I7 (user data) floors are also applied at construction:
neither may ever yield SAFE_TO_DELETE.

Phase 2 intentionally defines NO FileEntry/ScanResult/FolderAggregation — those
arrive in Phases 3/5. Deletion authority remains item-level (I10), which the
immutability of this dataclass supports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .enums import (
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)


def apply_confidence_gate(
    recommendation: DeletionRecommendation,
    confidence: ConfidenceLevel,
) -> DeletionRecommendation:
    """I9 — pure confidence gate.

    SAFE_TO_DELETE requires HIGH confidence; anything below forces REVIEW_FIRST.
    No other recommendation is ever changed (authority never increases under
    uncertainty, and never decreases when evidence is strong).
    """
    if (
        recommendation == DeletionRecommendation.SAFE_TO_DELETE
        and confidence is not ConfidenceLevel.HIGH
    ):
        return DeletionRecommendation.REVIEW_FIRST
    return recommendation


@dataclass(frozen=True)
class Assessment:
    """Immutable per-item safety assessment (three-axis model).

    Fields:
        impact: classified system/user impact of deleting this item.
        confidence: confidence in the classification (NOT in deletion safety).
        reason_key: stable, language-neutral reason identifier.
        recommendation: deletion recommendation. SAFE_TO_DELETE is only ever
            present alongside HIGH confidence, non-UNKNOWN impact, and no user
            data — enforced in ``__post_init__``.
        reason_params: interpolation params for the localized reason text.
        detected_category: knowledge-base category tag when one matched.
        app_id: owning application when identified (Phase 4 Tier 4+).
        is_user_data: personal/user-generated content flag (I7).
        is_temporary: recognized transient/temporary data flag.

    Invariants enforced at construction:
        I9 — SAFE_TO_DELETE ⇒ HIGH confidence.
        I3 (item level) — UNKNOWN impact ⇒ at most REVIEW_FIRST.
        I7 — is_user_data ⇒ at most REVIEW_FIRST.
    """

    impact: SystemImpact
    confidence: ConfidenceLevel
    reason_key: str
    recommendation: DeletionRecommendation = DeletionRecommendation.REVIEW_FIRST
    reason_params: Optional[Dict[str, object]] = None
    detected_category: Optional[str] = None
    app_id: Optional[str] = None
    is_user_data: bool = False
    is_temporary: bool = False

    def __post_init__(self) -> None:
        recommendation = apply_confidence_gate(self.recommendation, self.confidence)
        if recommendation == DeletionRecommendation.SAFE_TO_DELETE:
            if self.impact is SystemImpact.UNKNOWN or self.is_user_data:
                recommendation = DeletionRecommendation.REVIEW_FIRST
        object.__setattr__(self, "recommendation", recommendation)