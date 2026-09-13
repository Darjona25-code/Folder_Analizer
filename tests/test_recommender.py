"""Folder recommendation tests (Phase 5, roadmap §11 short-circuit rules).

These exercise ``derive_folder_recommendation`` with hand-built compositions —
the rule logic in isolation. The end-to-end canonical examples (compose +
derive over classification) live in ``test_folder_composition.py``.
"""

import pytest

from folder_analyzer.engine.enums import (
    CompositionBucket,
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from folder_analyzer.engine.models import Assessment, FolderComposition
from folder_analyzer.engine.recommender import (
    CompositionConfig,
    derive_folder_recommendation,
)


def _comp(
    d=0,
    uv=0,
    pc=0,
    knd=0,
    unk=0,
    *,
    by_category=None,
    total_bytes=None,
    not_resolvable_count=0,
) -> FolderComposition:
    total = (total_bytes if total_bytes is not None
             else d + uv + pc + knd + unk)
    return FolderComposition(
        total_bytes=total,
        disposable_bytes=d,
        user_value_bytes=uv,
        protected_critical_bytes=pc,
        known_non_disposable_bytes=knd,
        unknown_bytes=unk,
        not_resolvable_count=not_resolvable_count,
        by_category=dict(by_category or {}),
    )


# ---------------------------------------------------------------------------
# R1 — protected / critical (hard short-circuit).
# ---------------------------------------------------------------------------


def test_r1_pure_critical_is_critical_do_not_delete():
    a = derive_folder_recommendation(None, _comp(pc=100))
    assert a.impact is SystemImpact.CRITICAL
    assert a.recommendation is DeletionRecommendation.DO_NOT_DELETE
    assert a.confidence is ConfidenceLevel.HIGH
    assert a.reason_key == "r1_protected_critical"


def test_r1_mixed_is_high_do_not_delete():
    a = derive_folder_recommendation(None, _comp(d=50, pc=50))
    assert a.impact is SystemImpact.HIGH
    assert a.recommendation is DeletionRecommendation.DO_NOT_DELETE
    assert a.reason_key == "r1_protected_critical"


# ---------------------------------------------------------------------------
# R2 — user value (hard short-circuit); Downloads-policy floor.
# ---------------------------------------------------------------------------


def test_r2_user_value_is_review_first():
    a = derive_folder_recommendation(None, _comp(uv=100))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.impact is SystemImpact.NONE
    assert a.confidence is ConfidenceLevel.HIGH
    assert a.reason_key == "r2_user_value"


def test_r2_user_value_shadows_r5():
    # 90% disposable + 10% user-value: R2 fires BEFORE R5, never SAFE.
    a = derive_folder_recommendation(None, _comp(d=90, uv=10))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r2_user_value"


def test_r2_downloads_policy_floor():
    # ex8: Downloads category bytes -> LOW/REVIEW_FIRST/HIGH, policy reason.
    a = derive_folder_recommendation(
        None, _comp(d=100, by_category={"downloads": 100}),
    )
    assert a.impact is SystemImpact.LOW
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.confidence is ConfidenceLevel.HIGH
    assert a.reason_key == "downloads_policy"


def test_r2_downloads_policy_floors_even_pure_disposable():
    # Downloads-policy is a floor: even a 100% disposable Downloads folder is
    # REVIEW_FIRST (per-file assessments vary; folder-level consent required).
    a = derive_folder_recommendation(
        None, _comp(d=100, by_category={"downloads": 100}),
    )
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "downloads_policy"


# ---------------------------------------------------------------------------
# R3 — UNKNOWN (hard short-circuit, UNKNOWN_BLOCK = 0.0).
# ---------------------------------------------------------------------------


def test_r3_small_unknown_ceiling_ex4():
    # ex4: 5% UNKNOWN -> LOW/REVIEW_FIRST/MEDIUM.
    a = derive_folder_recommendation(None, _comp(d=95, unk=5))
    assert a.impact is SystemImpact.LOW
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.confidence is ConfidenceLevel.MEDIUM
    assert a.reason_key == "r3_unknown"


def test_r3_large_unknown_ex5():
    # ex5: 40% UNKNOWN -> UNKNOWN/REVIEW_FIRST/LOW.
    a = derive_folder_recommendation(None, _comp(d=60, unk=40))
    assert a.impact is SystemImpact.UNKNOWN
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.confidence is ConfidenceLevel.LOW
    assert a.reason_key == "r3_unknown"


def test_r3_any_unknown_blocks_safe_no_matter_majority():
    a = derive_folder_recommendation(None, _comp(d=999, unk=1))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r3_unknown"
    assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE


def test_r3_not_resolvable_flag_bumps_count():
    a = derive_folder_recommendation(
        None, _comp(d=95, unk=5, not_resolvable_count=1),
    )
    assert a.reason_key == "r3_unknown"


# ---------------------------------------------------------------------------
# R4 — KNOWN_NON_DISPOSABLE share >= REVIEW_SHARE.
# ---------------------------------------------------------------------------


def test_r4_known_share_review():
    a = derive_folder_recommendation(None, _comp(d=80, knd=20))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r4_known_non_disposable_share"


def test_r4_exactly_at_review_share_review():
    a = derive_folder_recommendation(None, _comp(d=85, knd=15))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r4_known_non_disposable_share"


# ---------------------------------------------------------------------------
# R5 — SAFE_TO_DELETE (positive evidence gate).
# ---------------------------------------------------------------------------


def test_r5_pure_disposable_is_safe_ex1():
    a = derive_folder_recommendation(None, _comp(d=100))
    assert a.impact is SystemImpact.NONE
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.confidence is ConfidenceLevel.HIGH
    assert a.reason_key == "r5_safe_to_delete"


def test_r5_known_ceiling_band_falls_to_r6():
    # 12% known: < REVIEW_SHARE (passes R4), > KNOWN_NON_DISPOSABLE_CEILING
    # (fails R5) -> R6 REVIEW_FIRST (the documented 10-15% band).
    a = derive_folder_recommendation(None, _comp(d=88, knd=12))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r6_review_first"


def test_r5_at_ceiling_safe():
    a = derive_folder_recommendation(None, _comp(d=90, knd=10))
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.reason_key == "r5_safe_to_delete"


def test_r5_config_override_thresholds():
    strict = CompositionConfig(safe_min_share=0.95)
    a = derive_folder_recommendation(None, _comp(d=90, knd=10), config=strict)
    assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE
    a2 = derive_folder_recommendation(None, _comp(d=96, knd=4), config=strict)
    assert a2.recommendation is DeletionRecommendation.SAFE_TO_DELETE


# ---------------------------------------------------------------------------
# Reason coherence / gate-on construction.
# ---------------------------------------------------------------------------


def test_folder_review_reason_is_never_safe_rationale():
    a = derive_folder_recommendation(None, _comp(d=90, unk=10))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r3_unknown"
    assert not a.reason_key.startswith("r5")


def test_folder_safe_always_meets_confidence_gate():
    # Whatever the rule input, the built Assessment must satisfy I9 (SAFE only
    # with HIGH confidence) — enforced via Assessment.__post_init__.
    a = derive_folder_recommendation(None, _comp(d=100))
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.confidence is ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Zero-byte trees.
# ---------------------------------------------------------------------------


def test_empty_tree_reviews_without_direct_evidence():
    a = derive_folder_recommendation(None, _comp(total_bytes=0))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "r6_review_first"


def test_empty_tree_safe_with_positive_direct_evidence():
    direct = Assessment(
        impact=SystemImpact.NONE,
        confidence=ConfidenceLevel.HIGH,
        reason_key="disposable_positive_evidence",
        recommendation=DeletionRecommendation.SAFE_TO_DELETE,
    )
    a = derive_folder_recommendation(direct, _comp(total_bytes=0))
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.reason_key == "r5_safe_to_delete"


def test_empty_tree_direct_review_stays_review():
    direct = Assessment(
        impact=SystemImpact.NONE,
        confidence=ConfidenceLevel.MEDIUM,
        reason_key="known_non_disposable",
        recommendation=DeletionRecommendation.REVIEW_FIRST,
    )
    a = derive_folder_recommendation(direct, _comp(total_bytes=0))
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST