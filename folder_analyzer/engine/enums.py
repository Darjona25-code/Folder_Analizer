"""Three-axis safety-model enums (Phase 2).

These enums are the single source of truth for the safety model's value spaces.
They are used by ``Assessment`` (models.py) and later by the recommendation
engine (Phase 5). Value spaces are fixed here; see docs/SAFETY.md for semantics.

Confidence is confidence *in the classification*, not confidence in the safety
of deletion — see docs/ROADMAP.md §5.
"""

from __future__ import annotations

from enum import Enum


class SystemImpact(str, Enum):
    """How strongly deletion of the item would affect the system/user."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DeletionRecommendation(str, Enum):
    """Final deletion recommendation an item or folder receives."""

    SAFE_TO_DELETE = "safe_to_delete"
    REVIEW_FIRST = "review_first"
    KEEP = "keep"
    DO_NOT_DELETE = "do_not_delete"


class ConfidenceLevel(str, Enum):
    """Confidence in the classification (NOT confidence in deletion safety)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompositionBucket(str, Enum):
    """Exhaustive, mutually exclusive descendant-byte buckets (roadmap §11).

    Every analyzed byte belongs to exactly one bucket; the five buckets sum to
    100% of descendant bytes (Phase 5 composition invariant, property-tested).

    - DISPOSABLE — known high-confidence disposable content (positive evidence).
    - USER_VALUE — personal/user-value content, or content the user may
      reasonably want (I7 floor: never SAFE_TO_DELETE).
    - PROTECTED_CRITICAL — protected Windows/system/application-critical
      content (I6 floor: never deletable).
    - KNOWN_NON_DISPOSABLE — understood/classified but not positively disposable.
    - UNKNOWN — insufficient evidence (I3 floor: at most REVIEW_FIRST;
      ``UNKNOWN_BLOCK = 0.0``).
    """

    DISPOSABLE = "disposable"
    USER_VALUE = "user_value"
    PROTECTED_CRITICAL = "protected_critical"
    KNOWN_NON_DISPOSABLE = "known_non_disposable"
    UNKNOWN = "unknown"