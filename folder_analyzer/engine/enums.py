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