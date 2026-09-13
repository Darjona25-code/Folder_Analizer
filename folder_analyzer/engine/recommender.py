"""Folder composition & recommendation (Phase 5, roadmap §11/§12).

Two pure functions, separated because they serve different consumers:

- ``compose`` — aggregates a folder's analyzed descendant ``FileEntry`` list
  into an exhaustive ``FolderComposition`` (the five mutually exclusive byte
  buckets). Pure arithmetic over the per-item ``bucket_for_entry`` mapping from
  ``classifier.py``; performs no classification itself.
- ``derive_folder_recommendation`` — turns a ``FolderComposition`` into the
  folder-level ``Assessment`` (impact / recommendation / confidence / reason)
  using the short-circuit rules R1-R6. The confidence gate (I9) is NOT
  re-implemented here: the returned ``Assessment`` is built through the
  construction-time gate in ``models.py``.

The research aligns exactly with roadmap §11 canonical examples:

+--------+----------------------------------+-------+--------------+------+
| ex     | composition                      | impact| rec          | conf |
+--------+----------------------------------+-------+--------------+------+
| 1      | 100% DISPOSABLE                  | NONE  | SAFE         | HIGH |
| 2      | 100% PROTECTED_CRITICAL          | CRIT  | DO_NOT_DELETE| HIGH |
| 3      | mixed disposable + critical      | HIGH  | DO_NOT_DELETE| HIGH |
| 4      | 95% DISPOSABLE + 5% UNKNOWN      | LOW   | REVIEW_FIRST | MED  |
| 5      | 60% DISPOSABLE + 40% UNKNOWN     | UNK   | REVIEW_FIRST | LOW  |
| 6      | user docs + app data             | NONE  | REVIEW_FIRST | HIGH |
| 7      | C:\\Users (protected)            | (excluded: I6 policy, not composition) |
| 8      | Downloads (policy)               | LOW   | REVIEW_FIRST | HIGH |
+--------+----------------------------------+-------+--------------+------+

Short-circuit order R1 -> R2 -> R3 -> R4/R5/R6:
- R1 any PROTECTED_CRITICAL bytes      -> DO_NOT_DELETE (CRITICAL iff 100%).
- R2 any USER_VALUE bytes              -> REVIEW_FIRST (policy floor when the
  folder holds Downloads-category bytes: LOW impact, ``downloads_policy``).
- R3 any UNKNOWN bytes (UNKNOWN_BLOCK=0) -> REVIEW_FIRST; >= UNKNOWN_HIGH_SHARE
  degrades impact->UNKNOWN, confidence->LOW (ex5), else LOW/MEDIUM (ex4).
- R4 KNOWN_NON_DISPOSABLE/TOTAL >= REVIEW_SHARE -> REVIEW_FIRST.
- R5 DISPOSABLE/TOTAL >= SAFE_MIN_SHARE AND KNOWN_NON_DISPOSABLE/TOTAL <=
  KNOWN_NON_DISPOSABLE_CEILING AND positive direct disposable evidence -> SAFE.
- R6 otherwise -> REVIEW_FIRST.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .classifier import bucket_for_entry
from .enums import (
    CompositionBucket,
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from .models import Assessment, FileEntry, FolderComposition


@dataclass(frozen=True)
class CompositionConfig:
    """Named heuristic thresholds (roadmap §11, initial defaults subject to
    validation). Implemented as named configurable constants."""

    safe_min_share: float = 0.85
    known_non_disposable_ceiling: float = 0.10
    review_share: float = 0.15
    unknown_block: float = 0.0
    # Impact/confidence demotion knee inside R3 (example 4 vs 5 boundary).
    unknown_high_share: float = 0.25
    # I9 — SAFE requires HIGH confidence; re-applied only as documentation
    # here, enforced at Assessment construction.
    confidence_gate: ConfidenceLevel = ConfidenceLevel.HIGH


def compose(
    entries: Iterable[FileEntry],
    *,
    total_bytes: Optional[int] = None,
) -> FolderComposition:
    """Aggregate analyzed FileEntries into an exhaustive FolderComposition.

    Every entry's size lands in exactly one bucket (per
    ``bucket_for_entry``), including zero-byte entries (bucket + 0 bytes).
    NOT_RESOLVABLE entries (reason_key "not_resolvable") aggregate their bytes
    into the UNKNOWN bucket (roadmap §11 NOT_RESOLVABLE aggregation).

    ``total_bytes`` defaults to the sum of the analyzed sizes; pass the
    aggregate size explicitly when the caller analyzed a partition whose byte
    total differs from the entries' sum (defensive; shares are computed against
    ``total_bytes``, never against a zero divisor).
    """
    buckets = {b: 0 for b in CompositionBucket}
    by_category: "dict[str, int]" = {}
    not_resolvable_count = 0
    total = 0
    for entry in entries:
        size = entry.size
        bucket = bucket_for_entry(entry)
        buckets[bucket] += size
        by_category[entry.category] = by_category.get(entry.category, 0) + size
        total += size
        if entry.assessment is not None and entry.assessment.reason_key == "not_resolvable":
            not_resolvable_count += 1
    if total_bytes is not None:
        total = total_bytes
    return FolderComposition(
        total_bytes=total,
        disposable_bytes=buckets[CompositionBucket.DISPOSABLE],
        user_value_bytes=buckets[CompositionBucket.USER_VALUE],
        protected_critical_bytes=buckets[CompositionBucket.PROTECTED_CRITICAL],
        known_non_disposable_bytes=buckets[CompositionBucket.KNOWN_NON_DISPOSABLE],
        unknown_bytes=buckets[CompositionBucket.UNKNOWN],
        not_resolvable_count=not_resolvable_count,
        by_category=dict(by_category),
    )


def derive_folder_recommendation(
    direct: Optional[Assessment],
    composition: FolderComposition,
    config: Optional[CompositionConfig] = None,
) -> Assessment:
    """Short-circuit folder-level recommendation (rules R1-R6).

    ``direct`` is the folder's own (item-level) assessment when one was
    computed; it is used only to resolve the empty-tree case (roadmap §11:
    "empty + positive direct evidence => SAFE; otherwise REVIEW_FIRST") — it
    NEVER overrides composition-derived short-circuits, and the returned
    folder Assessment never overrides per-item authority (I10).
    """
    cfg = config if config is not None else CompositionConfig()
    comp = composition

    if comp.total_bytes <= 0:
        # Zero-byte tree: resolved by direct folder assessment.
        if (
            direct is not None
            and direct.recommendation is DeletionRecommendation.SAFE_TO_DELETE
            and direct.confidence is cfg.confidence_gate
        ):
            return Assessment(
                impact=SystemImpact.NONE,
                confidence=cfg.confidence_gate,
                reason_key="r5_safe_to_delete",
                recommendation=DeletionRecommendation.SAFE_TO_DELETE,
            )
        return Assessment(
            impact=SystemImpact.NONE,
            confidence=ConfidenceLevel.MEDIUM,
            reason_key="r6_review_first",
            recommendation=DeletionRecommendation.REVIEW_FIRST,
        )

    # R1 (hard): any PROTECTED_CRITICAL byte short-circuits to DO_NOT_DELETE.
    if comp.protected_critical_bytes > 0:
        impact = (
            SystemImpact.CRITICAL
            if comp.share(CompositionBucket.PROTECTED_CRITICAL) >= 1.0
            else SystemImpact.HIGH
        )
        return Assessment(
            impact=impact,
            confidence=ConfidenceLevel.HIGH,
            reason_key="r1_protected_critical",
            recommendation=DeletionRecommendation.DO_NOT_DELETE,
            reason_params={
                "protected_share": comp.share(CompositionBucket.PROTECTED_CRITICAL),
            },
        )

    # Downloads-policy floor (roadmap §11 ex8, §12): a folder holding
    # Downloads-category content is LOW/REVIEW_FIRST/HIGH regardless of
    # composition ("policy; per-file assessments vary"). R1 already short-
    # circuited, so this check runs before the bucket short-circuits R2/R3.
    if comp.by_category.get("downloads", 0) > 0:
        return Assessment(
            impact=SystemImpact.LOW,
            confidence=ConfidenceLevel.HIGH,
            reason_key="downloads_policy",
            recommendation=DeletionRecommendation.REVIEW_FIRST,
        )

    # R2 (hard): any USER_VALUE byte short-circuits to at most REVIEW_FIRST.
    if comp.user_value_bytes > 0:
        return Assessment(
            impact=SystemImpact.NONE,
            confidence=ConfidenceLevel.HIGH,
            reason_key="r2_user_value",
            recommendation=DeletionRecommendation.REVIEW_FIRST,
        )

    # R3 (hard): any UNKNOWN byte blocks SAFE (UNKNOWN_BLOCK = 0.0).
    unknown_share = comp.share(CompositionBucket.UNKNOWN)
    if comp.unknown_bytes > 0:
        if unknown_share >= cfg.unknown_high_share:
            # ex5: 40% UNKNOWN -> UNKNOWN/LOW.
            impact, confidence = SystemImpact.UNKNOWN, ConfidenceLevel.LOW
        else:
            # ex4: 5% UNKNOWN -> LOW/MEDIUM.
            impact, confidence = SystemImpact.LOW, ConfidenceLevel.MEDIUM
        return Assessment(
            impact=impact,
            confidence=confidence,
            reason_key="r3_unknown",
            recommendation=DeletionRecommendation.REVIEW_FIRST,
            reason_params={"unknown_share": unknown_share},
        )

    # R4: KNOWN_NON_DISPOSABLE/TOTAL >= REVIEW_SHARE -> REVIEW_FIRST.
    known_share = comp.share(CompositionBucket.KNOWN_NON_DISPOSABLE)
    if known_share >= cfg.review_share:
        return Assessment(
            impact=SystemImpact.NONE,
            confidence=ConfidenceLevel.MEDIUM,
            reason_key="r4_known_non_disposable_share",
            recommendation=DeletionRecommendation.REVIEW_FIRST,
            reason_params={
                "known_share": known_share,
                "review_share": cfg.review_share,
            },
        )

    # R5: at this point DISPOSABLE + KNOWN_NON_DISPOSABLE == 100%.
    disposable_share = comp.share(CompositionBucket.DISPOSABLE)
    positive_direct_disposable_evidence = (
        comp.share(CompositionBucket.DISPOSABLE) > 0
    )
    if (
        disposable_share >= cfg.safe_min_share
        and known_share <= cfg.known_non_disposable_ceiling
        and positive_direct_disposable_evidence
    ):
        return Assessment(
            impact=SystemImpact.NONE,
            confidence=cfg.confidence_gate,
            reason_key="r5_safe_to_delete",
            recommendation=DeletionRecommendation.SAFE_TO_DELETE,
            reason_params={
                "disposable_share": disposable_share,
                "safe_min_share": cfg.safe_min_share,
                "known_non_disposable_ceiling": cfg.known_non_disposable_ceiling,
            },
        )

    # R6: otherwise.
    return Assessment(
        impact=SystemImpact.NONE,
        confidence=ConfidenceLevel.MEDIUM,
        reason_key="r6_review_first",
        recommendation=DeletionRecommendation.REVIEW_FIRST,
    )


__all__ = [
    "CompositionConfig",
    "compose",
    "derive_folder_recommendation",
]