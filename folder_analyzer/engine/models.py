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

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from .enums import (
    CompositionBucket,
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


@dataclass(frozen=True, slots=True)
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
    Reason/explainability coherence: when a requested SAFE_TO_DELETE is demoted
    (I9/I3/I7), ``reason_key``/``reason_params`` are rewritten to the reason for
    the demotion — a REVIEW_FIRST result never keeps a safe-to-delete rationale.
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
        requested = self.recommendation
        recommendation = apply_confidence_gate(requested, self.confidence)
        if recommendation is DeletionRecommendation.SAFE_TO_DELETE:
            if self.impact is SystemImpact.UNKNOWN or self.is_user_data:
                recommendation = DeletionRecommendation.REVIEW_FIRST
        reason_key = self.reason_key
        reason_params = self.reason_params
        if (
            requested is DeletionRecommendation.SAFE_TO_DELETE
            and recommendation is not DeletionRecommendation.SAFE_TO_DELETE
        ):
            if self.is_user_data:
                reason_key, reason_params = "user_data", None
            elif self.impact is SystemImpact.UNKNOWN:
                reason_key, reason_params = "uncertain", None
            else:
                reason_key = "confidence_gate_promoted"
                reason_params = {
                    "confidence": " ".join(
                        w.capitalize() for w in self.confidence.value.split("_")
                    )
                }
        object.__setattr__(self, "recommendation", recommendation)
        object.__setattr__(self, "reason_key", reason_key)
        object.__setattr__(self, "reason_params", reason_params)


# ---------------------------------------------------------------------------
# Phase 3 — File Analysis & Data Model
#
# FileEntry: per-file metadata collected during the scan traversal with zero
# additional syscalls (reuses the DirEntry data + the single existing
# entry.stat(follow_symlinks=False) call). No classification here — that is
# Phase 4 (knowledge base) / Phase 5 (recommendation engine). In Phase 3 every
# record carries category="unknown" and assessment=None.
#
# Three-stage record lifecycle (roadmap §8): DISCOVERED -> ANALYZED -> RETAINED.
# ANALYZED covers 100% of accessible files; RETAINED is the bounded, prioritized
# subset kept in memory by the retention store. Eviction never reduces the
# ANALYZED count.
# ---------------------------------------------------------------------------


class AnalysisState(Enum):
    """Record lifecycle state (roadmap §8 three-stage model)."""

    DISCOVERED = "discovered"
    ANALYZED = "analyzed"
    RETAINED = "retained"


@dataclass(frozen=True)
class FileEntry:
    """Per-file metadata record (Phase 3 — metadata only, no classification).

    Build cost: reuses the DirEntry handed out by ``os.scandir`` plus the one
    ``entry.stat(follow_symlinks=False)`` call the scanner already made for the
    file size — no additional syscalls are issued to populate this record.

    ``created_ts`` is ``st_ctime`` -> creation time on Windows, inode-change
    time on POSIX. ``attributes`` carries the raw stat fields the scanner
    observes (mode/ino/nlink/symlink flag), not a classification.

    ``assessment`` is a Phase 5 placeholder and is None throughout Phase 3/4.
    ``is_representative`` is set by the retention sampler (one record per
    (folder, category) survives eviction preferentially).
    """

    path: str
    filename: str
    extension: str
    size: int
    created_ts: Optional[float]
    modified_ts: Optional[float]
    accessed_ts: Optional[float]
    attributes: Dict[str, object]
    assessment: Optional[Assessment] = None
    category: str = "unknown"
    is_representative: bool = False
    analysis_state: AnalysisState = AnalysisState.ANALYZED

    @property
    def is_user_data(self) -> bool:
        return bool(self.assessment and self.assessment.is_user_data)


@dataclass(frozen=True)
class FolderComposition:
    """Exhaustive descendant-byte composition (Phase 5, roadmap §11).

    The five buckets are mutually exclusive and cover every analyzed byte:
    ``disposable + user_value + protected_critical + known_non_disposable +
    unknown == total_bytes`` (invariant property-tested). ``total_bytes`` is the
    sum of the sizes of the analyzed descendants in scope; zero-byte files carry
    a bucket but contribute 0 bytes, so percentages are over ``total_bytes``.

    ``by_category`` maps the raw KB category (e.g. ``cache``, ``documents``) to
    byte totals, so folder-level impact derivation can recover category-level
    nuance (e.g. ``documents`` vs ``downloads`` user-value impact) that a flat
    bucket mask loses.

    ``not_resolvable_count`` counts descendants flagged NOT_RESOLVABLE (Case B,
    LOW confidence); their bytes are aggregated into the UNKNOWN bucket (R3).
    """

    total_bytes: int = 0
    disposable_bytes: int = 0
    user_value_bytes: int = 0
    protected_critical_bytes: int = 0
    known_non_disposable_bytes: int = 0
    unknown_bytes: int = 0
    not_resolvable_count: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)

    @property
    def buckets(self) -> Dict[CompositionBucket, int]:
        return {
            CompositionBucket.DISPOSABLE: self.disposable_bytes,
            CompositionBucket.USER_VALUE: self.user_value_bytes,
            CompositionBucket.PROTECTED_CRITICAL: self.protected_critical_bytes,
            CompositionBucket.KNOWN_NON_DISPOSABLE: self.known_non_disposable_bytes,
            CompositionBucket.UNKNOWN: self.unknown_bytes,
        }

    def share(self, bucket: CompositionBucket) -> float:
        """Byte share of *bucket*, 0.0 when total_bytes is 0."""
        if self.total_bytes <= 0:
            return 0.0
        return self.buckets[bucket] / self.total_bytes


@dataclass(frozen=True)
class FolderAggregation:
    """Per-folder aggregation over ALL analyzed files (roadmap §8/§9).

    ``files_analyzed`` ALWAYS equals 100% of the accessible files in the
    folder's direct scan set, regardless of how many ``records_retained`` were
    kept after eviction. In Phase 3 every record is unclassified; from Phase 5
    the ``by_impact`` / ``by_recommendation`` / ``by_confidence`` dicts,
    ``app_ids``, the protected/unknown/user_data tallies, and ``composition``
    are populated with real classifications over the folder's direct analyzed
    bytes. ``assessment`` carries the folder's derived recommendation
    (roadmap §11 short-circuit composition); it never overrides item-level
    authority (I10).
    """

    files_analyzed: int = 0
    records_retained: int = 0
    total_descendant_size: int = 0
    by_impact: Dict[SystemImpact, int] = field(
        default_factory=lambda: {i: 0 for i in SystemImpact}
    )
    by_recommendation: Dict[DeletionRecommendation, int] = field(
        default_factory=lambda: {r: 0 for r in DeletionRecommendation}
    )
    by_confidence: Dict[ConfidenceLevel, int] = field(
        default_factory=lambda: {c: 0 for c in ConfidenceLevel}
    )
    protected_count: int = 0
    protected_size: int = 0
    unknown_count: int = 0
    unknown_size: int = 0
    user_data_count: int = 0
    user_data_size: int = 0
    app_ids: Dict[str, int] = field(default_factory=dict)
    composition: Optional[FolderComposition] = None
    assessment: Optional[Assessment] = None


@dataclass(frozen=True)
class ScanResult:
    """Whole-scan summary (roadmap §11 'integrated ScanResult').

    ``files_analyzed`` is the total over all folders and always equals 100% of
    the accessible files found; it is independent of ``records_retained``.
    ``per_folder`` maps normalized folder path -> ``FolderAggregation``.
    Folders whose retained records were all evicted are still present here with
    full ``files_analyzed`` counts (their records are re-computed on demand by
    the scanner's re-analysis path, not lost).
    """

    root_path: str
    files_analyzed: int = 0
    records_retained: int = 0
    total_descendant_size: int = 0
    inaccessible_count: int = 0
    folder_errors: Tuple[str, ...] = ()
    per_folder: Dict[str, FolderAggregation] = field(default_factory=dict)