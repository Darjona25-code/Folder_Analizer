"""Scan-time classifier (Phase 5): wires Knowledge Base verdicts into Assessments.

This is the FIRST point in the pipeline where ``Assessment`` objects get
populated with real (non-None) data. Every safety invariant (I1-I3, I7, I9,
I10) depends on the mappings below being correct, so they are a single explicit
policy table rather than scattered logic.

Boundaries:

- The KB produces ``KBResult`` classification verdicts only (categories, tiers,
  confidence hints).
- The classifier turns a path (or ``FileEntry``) into a concrete, immutable
  ``Assessment``: impact, recommendation, confidence, reason_key, plus the
  Phase 5 attribution fields (``detected_category``, ``app_id``,
  ``is_user_data``, ``is_temporary``).
- The classifier performs NO file I/O. Level-1 path classification only; the
  KB's bounded Level 2/3 content analysis stays an explicit, on-demand step
  (``kb.classify_content``) — the scanner still never reads file contents.
- The five composition buckets (``CompositionBucket``) are derived here so the
  recommender and the aggregation pipeline share one mapping.

Unknown stays unknown: any category without a policy entry (e.g. future KB
additions) degrades to the UNKNOWN bucket, REVIEW_FIRST, LOW — never a forced
positive guess. This honors I1 (uncertainty never increases deletion authority).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from .enums import (
    CompositionBucket,
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from .kb import classify as kb_classify, classify_scan_path
from .kb._norm import components, norm
from .models import Assessment, FileEntry

__all__ = [
    "CATEGORY_POLICY",
    "CategoryPolicy",
    "ScanAssessment",
    "assessment_from_scan_record",
    "classify_entry",
    "classify_path",
    "classify_scan",
    "bucket_for_category",
    "bucket_for_entry",
    "bucket_for_assessment",
]

# ---------------------------------------------------------------------------
# Category policy table — the single source of mapping truth.
#
# ``confidence_hint`` from the KB tier is refined here: positive-evidence
# disposable categories (explicit cache/temp purpose markers) are asserted HIGH,
# because the DIRECTORY NAME is high-confidence positive evidence of disposable
# purpose (roadmap §12 "positive-evidence categories"). Tier 2/4 pattern
# categories (``dev``, ``ai_ml``, ``app:*``, …) keep MEDIUM.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScanAssessment:
    """Lightweight, allocation-lean per-item classification (Phase 5 scan path).

    Carries exactly the fields the 50k-file scan actually consumes (counters,
    bucket tallies, retention priority, retained-record materialization) without
    the full ``Assessment`` object / ``__post_init__`` construction. The full
    ``Assessment`` is materialized lazily — from this record — only for the
    RETAINED subset via ``assessment_from_scan_record``. Fields are the *final*
    (post-gate) values: policy floors (I9/I3/I7) are policy-encoded, so no
    construction-time gate can diverge them (``Assessment`` re-applies the gate
    idempotently).
    """

    impact: SystemImpact
    confidence: ConfidenceLevel
    reason_key: str
    recommendation: DeletionRecommendation
    reason_params: Optional[Dict[str, object]]
    detected_category: Optional[str]
    app_id: Optional[str]
    is_user_data: bool
    is_temporary: bool
    bucket: CompositionBucket


@dataclass(frozen=True)
class CategoryPolicy:
    bucket: CompositionBucket
    impact: SystemImpact
    confidence: ConfidenceLevel
    recommendation: DeletionRecommendation
    is_user_data: bool
    is_temporary: bool


CATEGORY_POLICY: "dict[str, CategoryPolicy]" = {
    # --- protected / system-critical (I6 floor) ---
    "system": CategoryPolicy(
        CompositionBucket.PROTECTED_CRITICAL, SystemImpact.CRITICAL,
        ConfidenceLevel.HIGH, DeletionRecommendation.DO_NOT_DELETE, False, False,
    ),
    "program_files": CategoryPolicy(
        CompositionBucket.PROTECTED_CRITICAL, SystemImpact.CRITICAL,
        ConfidenceLevel.HIGH, DeletionRecommendation.DO_NOT_DELETE, False, False,
    ),
    "program_files_x86": CategoryPolicy(
        CompositionBucket.PROTECTED_CRITICAL, SystemImpact.CRITICAL,
        ConfidenceLevel.HIGH, DeletionRecommendation.DO_NOT_DELETE, False, False,
    ),
    "program_data": CategoryPolicy(
        CompositionBucket.PROTECTED_CRITICAL, SystemImpact.HIGH,
        ConfidenceLevel.HIGH, DeletionRecommendation.DO_NOT_DELETE, False, False,
    ),
    # --- positive-evidence disposable (I2 / I9: SAFE requires HIGH) ---
    "temp": CategoryPolicy(
        CompositionBucket.DISPOSABLE, SystemImpact.NONE,
        ConfidenceLevel.HIGH, DeletionRecommendation.SAFE_TO_DELETE, False, True,
    ),
    "cache": CategoryPolicy(
        CompositionBucket.DISPOSABLE, SystemImpact.NONE,
        ConfidenceLevel.HIGH, DeletionRecommendation.SAFE_TO_DELETE, False, True,
    ),
    "browser": CategoryPolicy(  # refined non-disposable unless under a marker dir
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.NONE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    # --- app data / understood-but-not-disposable (I7-adjacent floors) ---
    "app_data_local": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app_data_roaming": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "config": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "dev": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.LOW,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "ai_ml": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.LOW,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "game": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.MODERATE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "docker": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.MODERATE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app:ollama": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.MODERATE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app:docker": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.MODERATE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app:python": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.MODERATE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app:node": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.LOW,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app:browser": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.MODERATE,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    "app": CategoryPolicy(
        CompositionBucket.KNOWN_NON_DISPOSABLE, SystemImpact.HIGH,
        ConfidenceLevel.MEDIUM, DeletionRecommendation.REVIEW_FIRST, False, False,
    ),
    # --- user value (I7 floor: never SAFE_TO_DELETE) ---
    "documents": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
    "downloads": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
    "desktop": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
    "user_profile": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
    "media": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
    "archives": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
    "databases": CategoryPolicy(
        CompositionBucket.USER_VALUE, SystemImpact.LOW,
        ConfidenceLevel.HIGH, DeletionRecommendation.REVIEW_FIRST, True, False,
    ),
}

# Explicit disposable-purpose directory markers. When a ``browser``-branded path
# (e.g. ``...\\Chrome\\Cache\\...``) has one of these components, the PURPOSE is
# high-confidence disposable and the bucket is DISPOSABLE (not an app install).
_DISPOSABLE_MARKERS: "frozenset[str]" = frozenset({
    "cache", "caches", "cache2", "cache_data", "code cache", "code_cache",
    "gpu cache", "gpu_cache", ".cache", "temporary internet files",
    "service worker", "service worker cache", "sw_cache", "offline cache",
})


def _policy_for(category: str) -> CategoryPolicy:
    if category == "unknown":
        return CategoryPolicy(
            CompositionBucket.UNKNOWN, SystemImpact.UNKNOWN,
            ConfidenceLevel.LOW, DeletionRecommendation.REVIEW_FIRST, False, False,
        )
    return CATEGORY_POLICY.get(
        category,
        CategoryPolicy(
            CompositionBucket.UNKNOWN, SystemImpact.UNKNOWN,
            ConfidenceLevel.LOW, DeletionRecommendation.REVIEW_FIRST, False, False,
        ),
    )


def bucket_for_category(category: str, path: str = "") -> CompositionBucket:
    """Resolve a KB category to its composition bucket.

    ``browser`` is refined by path components: under an explicit disposable
    marker directory (``Chrome\\Cache``, …) it is DISPOSABLE, otherwise it is a
    browser application tree (KNOWN_NON_DISPOSABLE).
    """
    if category == "browser" and path:
        parts = components(path)
        if parts and any(part in _DISPOSABLE_MARKERS for part in parts):
            return CompositionBucket.DISPOSABLE
    return _policy_for(category).bucket


def bucket_for_assessment(assessment: Assessment, path: str) -> CompositionBucket:
    """Bucket for an Assessment + its path.

    Items flagged NOT_RESOLVABLE (reason_key "not_resolvable") aggregate as
    UNKNOWN-category bytes (roadmap §11: any folder with a NOT_RESOLVABLE
    descendant stays at most REVIEW_FIRST via R3, ``UNKNOWN_BLOCK = 0.0``).
    """
    if assessment is not None and assessment.reason_key == "not_resolvable":
        return CompositionBucket.UNKNOWN
    return bucket_for_category(assessment.detected_category or "unknown", path)


def bucket_for_entry(entry: FileEntry) -> CompositionBucket:
    """Bucket for a classified FileEntry (assessment-aware when present)."""
    if entry.assessment is not None:
        return bucket_for_assessment(entry.assessment, entry.path)
    return bucket_for_category(entry.category, entry.path)


_REASON_BY_BUCKET: "dict[CompositionBucket, str]" = {
    CompositionBucket.PROTECTED_CRITICAL: "protected_critical",
    CompositionBucket.DISPOSABLE: "disposable_positive_evidence",
    CompositionBucket.USER_VALUE: "user_value",
    CompositionBucket.KNOWN_NON_DISPOSABLE: "known_non_disposable",
    CompositionBucket.UNKNOWN: "unknown_impact",
}

# ScanAssessment is a fully immutable record whose fields are a pure function
# of (detected_category, bucket). Sharing one instance per distinct verdict
# preserves value semantics (I10 item authority reads fields only) while
# removing per-file dataclass construction from the 50k-file scan path and the
# associated allocation peak.
_SCAN_RECORDS: "dict[tuple[str, CompositionBucket], ScanAssessment]" = {}


def classify_path(
    path: str,
    *,
    filename: Optional[str] = None,
    not_resolvable: bool = False,
) -> Assessment:
    """Classify one path into a concrete, immutable Assessment.

    Args:
        path: the file path to classify (normalized/normal-case is internal).
        filename: the basename, when already known (avoids a second basename()).
        not_resolvable: when True the path cannot be safely resolved (Case B,
            LOW confidence) and classifies as UNKNOWN/REVIEW_FIRST with the
            ``not_resolvable`` reason — the NOT_RESOLVABLE -> UNKNOWN pipeline.

    Returns an Assessment whose invariants are enforced at Construction
    (__post_init__ applies I9/I3/I7 floors), so no caller can build an
    unrepresentable SAFE_TO_DELETE.
    """
    return assessment_from_scan_record(
        classify_scan(path, filename=filename, not_resolvable=not_resolvable)
    )


def classify_scan(
    path: str,
    *,
    filename: Optional[str] = None,
    not_resolvable: bool = False,
    _ctx: "Optional[ScanFolderContext]" = None,
) -> ScanAssessment:
    """Classification record for the scan path (allocation-lean; see
    ``ScanAssessment``). Same verdict as ``classify_path`` by construction.

    ``_ctx`` is the per-folder ``kb.ScanFolderContext`` from
    ``prepare_scan_folder``: when supplied, the scan hot path reuses the
    folder's pre-resolved tiers 0/1/5 and shareable component list instead of
    re-running every tier per file. The verdict is byte-identical to the
    standalone path (``kb.classify``), which remains the default.
    """
    if not_resolvable:
        return ScanAssessment(
            impact=SystemImpact.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
            reason_key="not_resolvable",
            recommendation=DeletionRecommendation.REVIEW_FIRST,
            reason_params=None,
            detected_category="unknown",
            app_id=None,
            is_user_data=False,
            is_temporary=False,
            bucket=CompositionBucket.UNKNOWN,
        )
    if _ctx is not None:
        if filename is not None and os.altsep not in filename \
                and os.sep not in filename and filename not in (".", ".."):
            file_key = _ctx.folder_key + os.sep + filename.lower()
        else:
            file_key = norm(path)
        file_name = filename if filename is not None else os.path.basename(path)
        kb_result = classify_scan_path(_ctx, file_key=file_key, file_name=file_name)
    else:
        kb_result = kb_classify(path)
    policy = _policy_for(kb_result.category)

    # ``browser`` paths under an explicit disposable marker directory
    # (e.g. ``Chrome\Cache``) are DISPOSABLE positive evidence, not an app tree.
    bucket = bucket_for_category(kb_result.category, path)
    if (
        bucket is CompositionBucket.DISPOSABLE
        and policy.bucket is not CompositionBucket.DISPOSABLE
    ):
        policy = CategoryPolicy(
            CompositionBucket.DISPOSABLE, SystemImpact.NONE,
            ConfidenceLevel.HIGH, DeletionRecommendation.SAFE_TO_DELETE,
            False, True,
        )

    app_id: Optional[str] = None
    if kb_result.category.startswith("app"):
        app_id = kb_result.category.split(":", 1)[1] if ":" in kb_result.category else kb_result.category
    elif kb_result.category == "app":
        app_id = "installed"

    memo_key = (kb_result.category, bucket)
    rec = _SCAN_RECORDS.get(memo_key)
    if rec is None:
        rec = ScanAssessment(
            impact=policy.impact,
            confidence=policy.confidence,
            reason_key=_REASON_BY_BUCKET[bucket],
            recommendation=policy.recommendation,
            reason_params=None,
            detected_category=kb_result.category,
            app_id=app_id,
            is_user_data=policy.is_user_data,
            is_temporary=policy.is_temporary,
            bucket=bucket,
        )
        _SCAN_RECORDS[memo_key] = rec
    return rec


def assessment_from_scan_record(record: ScanAssessment) -> Assessment:
    """Materialize the full Assessment for a retained record.

    Idempotent: rebuilding an Assessment from an already-gated ScanAssessment
    re-applies I9/I3/I7 gates without changing the verdict (policy floors are
    encoded in the record). Real ``Assessment`` values pass through unchanged.
    """
    if isinstance(record, Assessment):
        return record
    return Assessment(
        impact=record.impact,
        confidence=record.confidence,
        reason_key=record.reason_key,
        recommendation=record.recommendation,
        reason_params=record.reason_params,
        detected_category=record.detected_category,
        app_id=record.app_id,
        is_user_data=record.is_user_data,
        is_temporary=record.is_temporary,
    )


def classify_entry(entry: FileEntry, *, not_resolvable: bool = False) -> Assessment:
    """Classify a FileEntry; convenience for the scan-pipeline call sites."""
    return classify_path(
        entry.path,
        filename=entry.filename,
        not_resolvable=not_resolvable,
    )