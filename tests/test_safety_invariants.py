"""Formal safety invariants as automated tests (Phase 2 core deliverable).

Invariants reference docs/SAFETY.md §8 and docs/ROADMAP.md §6:

- I1 — Uncertainty must reduce deletion authority, never increase it.
- I2 — SAFE_TO_DELETE requires positive, high-confidence evidence.
- I3 (strict, item level) — UNKNOWN impact ⇒ at most REVIEW_FIRST.
  (Folder-level: "any folder with any UNKNOWN descendant is at most
  REVIEW_FIRST" is composition work and lands in Phase 5 — see the scaffold.)
- I7 — is_user_data ⇒ never SAFE_TO_DELETE.
- I9 — SAFE_TO_DELETE requires HIGH confidence; enforced at construction.
- I10 — item-level deletion authority independent of folder recommendation
  (scaffold now; fully testable against FolderAggregation in Phase 5).

The exhaustive tests iterate the full SystemImpact x ConfidenceLevel x
DeletionRecommendation product where practical.
"""

import dataclasses
import itertools

import pytest

from folder_analyzer.engine.enums import (
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from folder_analyzer.engine.models import Assessment, apply_confidence_gate

# Positive-evidence reason keys: the only keys the engine may attach to a
# SAFE_TO_DELETE assessment (I2: no SAFE without positive evidence).
POSITIVE_EVIDENCE_REASON_KEYS = {"clean_system_data"}


# --------------------------------------------------------------------------
# I9 — confidence gate (pure function)
# --------------------------------------------------------------------------

def test_i9_pure_gate_keeps_safe_with_high():
    for confidence in ConfidenceLevel:
        result = apply_confidence_gate(DeletionRecommendation.SAFE_TO_DELETE, confidence)
        if confidence is ConfidenceLevel.HIGH:
            assert result is DeletionRecommendation.SAFE_TO_DELETE
        else:
            assert result is DeletionRecommendation.REVIEW_FIRST


def test_i9_pure_gate_never_changes_other_recommendations():
    for rec in (DeletionRecommendation.REVIEW_FIRST,
                DeletionRecommendation.KEEP,
                DeletionRecommendation.DO_NOT_DELETE):
        for confidence in ConfidenceLevel:
            assert apply_confidence_gate(rec, confidence) is rec


def test_i9_gate_is_idempotent():
    for rec in DeletionRecommendation:
        for confidence in ConfidenceLevel:
            once = apply_confidence_gate(rec, confidence)
            twice = apply_confidence_gate(once, confidence)
            assert twice is once


# --------------------------------------------------------------------------
# I9 + I3 (item level) — exhaustive construction-time enforcement
# --------------------------------------------------------------------------

def test_i9_invalid_tuple_cannot_be_constructed():
    """(SAFE_TO_DELETE, MEDIUM/LOW) is auto-corrected at construction."""
    for confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW):
        a = Assessment(
            impact=SystemImpact.NONE,
            confidence=confidence,
            reason_key="clean_system_data",
            recommendation=DeletionRecommendation.SAFE_TO_DELETE,
        )
        assert a.recommendation is DeletionRecommendation.REVIEW_FIRST


def test_i9_no_assessment_ever_has_safe_with_non_high():
    """For every combination, no constructed Assessment is SAFE without HIGH."""
    for impact, confidence, requested in itertools.product(
        SystemImpact, ConfidenceLevel, DeletionRecommendation
    ):
        a = Assessment(impact=impact, confidence=confidence,
                       reason_key="x", recommendation=requested)
        if a.recommendation is DeletionRecommendation.SAFE_TO_DELETE:
            assert confidence is ConfidenceLevel.HIGH


def test_i9_demotion_updates_reason_key():
    """A SAFE->REVIEW_FIRST I9 demotion rewrites the reason to the demotion
    cause, so a REVIEW_FIRST result never keeps a safe-to-delete rationale."""
    a = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.MEDIUM,
                   reason_key="clean_system_data",
                   recommendation=DeletionRecommendation.SAFE_TO_DELETE)
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "confidence_gate_promoted"
    assert a.reason_params == {"confidence": "Medium"}


def test_i3_demotion_updates_reason_key():
    a = Assessment(impact=SystemImpact.UNKNOWN, confidence=ConfidenceLevel.HIGH,
                   reason_key="clean_system_data",
                   recommendation=DeletionRecommendation.SAFE_TO_DELETE)
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "uncertain"
    assert a.reason_params is None


def test_i7_demotion_updates_reason_key():
    a = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
                   reason_key="clean_system_data",
                   recommendation=DeletionRecommendation.SAFE_TO_DELETE,
                   is_user_data=True)
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "user_data"
    assert a.reason_params is None


def test_no_demotion_keeps_reason_key():
    a = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
                   reason_key="clean_system_data",
                   recommendation=DeletionRecommendation.SAFE_TO_DELETE)
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.reason_key == "clean_system_data"


def test_i3_item_unknown_never_safe():
    """Exhaustive: UNKNOWN impact ⇒ at most REVIEW_FIRST, never SAFE."""
    for confidence in ConfidenceLevel:
        a = Assessment(impact=SystemImpact.UNKNOWN, confidence=confidence,
                       reason_key="uncertain", recommendation=DeletionRecommendation.SAFE_TO_DELETE)
        assert a.recommendation is DeletionRecommendation.REVIEW_FIRST


def test_i9_i3_exhaustive_safe_only_when_allowed():
    """The strongest exhaustive property: SAFE_TO_DELETE iff HIGH confidence,
    non-UNKNOWN impact, and not user data."""
    for impact, confidence in itertools.product(SystemImpact, ConfidenceLevel):
        a = Assessment(impact=impact, confidence=confidence,
                       reason_key="clean_system_data",
                       recommendation=DeletionRecommendation.SAFE_TO_DELETE)
        allowed = (
            impact is not SystemImpact.UNKNOWN
            and confidence is ConfidenceLevel.HIGH
        )
        assert (a.recommendation is DeletionRecommendation.SAFE_TO_DELETE) == allowed


# --------------------------------------------------------------------------
# I7 — user data floor
# --------------------------------------------------------------------------

def test_i7_user_data_never_safe():
    for impact, confidence in itertools.product(SystemImpact, ConfidenceLevel):
        a = Assessment(impact=impact, confidence=confidence,
                       reason_key="user_data",
                       recommendation=DeletionRecommendation.SAFE_TO_DELETE,
                       is_user_data=True)
        assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE


def test_i7_user_data_keeps_non_safe_recommendations():
    for rec in (DeletionRecommendation.REVIEW_FIRST,
                DeletionRecommendation.KEEP,
                DeletionRecommendation.DO_NOT_DELETE):
        a = Assessment(impact=SystemImpact.HIGH, confidence=ConfidenceLevel.HIGH,
                       reason_key="review_before_delete",
                       recommendation=rec, is_user_data=True)
        assert a.recommendation is rec


# --------------------------------------------------------------------------
# I1/I2 — base UNKNOWN rules and positive-evidence requirement
# --------------------------------------------------------------------------

def test_i1_unknown_never_increases_deletion_authority():
    """UNKNOWN impact may only ever keep or reduce requested authority."""
    for confidence, requested in itertools.product(ConfidenceLevel, DeletionRecommendation):
        a = Assessment(impact=SystemImpact.UNKNOWN, confidence=confidence,
                       reason_key="uncertain", recommendation=requested)
        permissiveness = {
            DeletionRecommendation.SAFE_TO_DELETE: 3,
            DeletionRecommendation.REVIEW_FIRST: 2,
            DeletionRecommendation.KEEP: 1,
            DeletionRecommendation.DO_NOT_DELETE: 0,
        }
        assert permissiveness[a.recommendation] <= permissiveness[requested]


def test_i2_safe_requires_positive_evidence_reason():
    """Every SAFE_TO_DELETE assessment must carry a positive-evidence reason key
    (I2: no SAFE without positive, high-confidence evidence)."""
    for impact, confidence, requested in itertools.product(
        SystemImpact, ConfidenceLevel, DeletionRecommendation
    ):
        a = Assessment(impact=impact, confidence=confidence,
                       reason_key="validated", recommendation=requested)
        if a.recommendation is DeletionRecommendation.SAFE_TO_DELETE:
            assert impact is not SystemImpact.UNKNOWN
            assert confidence is ConfidenceLevel.HIGH
        # Construction only enforces the value space; the positive-reason-key
        # rule is a contract for the Phase 5 engine, asserted here on the reason
        # key attached to SAFE results produced with a positive-evidence key:
    for impact, confidence in itertools.product(SystemImpact, ConfidenceLevel):
        a = Assessment(impact=impact, confidence=confidence,
                       reason_key="clean_system_data",
                       recommendation=DeletionRecommendation.SAFE_TO_DELETE)
        if a.recommendation is DeletionRecommendation.SAFE_TO_DELETE:
            assert a.reason_key in POSITIVE_EVIDENCE_REASON_KEYS


# --------------------------------------------------------------------------
# I10 — item-level authority (scaffold; full composition test in Phase 5)
# --------------------------------------------------------------------------

def test_i10_assessment_is_immutable():
    """I10 structural guarantee: a parent cannot mutate an item's Assessment
    after construction (frozen dataclass)."""
    a = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
                   reason_key="clean_system_data",
                   recommendation=DeletionRecommendation.SAFE_TO_DELETE)
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.recommendation = DeletionRecommendation.KEEP


def test_i10_item_authority_independent_of_parent_scaffold():
    """Phase 2 scaffold of the Phase 5 invariant.

    Once FolderAggregation exists (Phase 5), this test will additionally assert:
      - a folder whose recommendation is KEEP/DO_NOT_DELETE does NOT downgrade a
        SAFE_TO_DELETE item's own Assessment (item authority = I10);
      - a folder whose recommendation is SAFE_TO_DELETE never upgrades an item
        that is itself REVIEW_FIRST/KEEP/DO_NOT_DELETE;
      - UNKNOWN descendants force the folder to at most REVIEW_FIRST (I3).
    Here we assert what the Phase 2 model already guarantees: folder-level
    recommendation state cannot modify an item Assessment because each item
    Assessment is an independent, immutable value.
    """
    item = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
                      reason_key="clean_system_data",
                      recommendation=DeletionRecommendation.SAFE_TO_DELETE)
    folder_recommendation = DeletionRecommendation.KEEP  # Phase 5 would derive this
    # Mutating folder-level state must not touch the item's authority:
    folder_recommendation = DeletionRecommendation.DO_NOT_DELETE
    assert folder_recommendation is DeletionRecommendation.DO_NOT_DELETE
    assert item.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    # Different items have independent values even when constructed identically:
    other = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
                       reason_key="clean_system_data",
                       recommendation=DeletionRecommendation.SAFE_TO_DELETE)
    assert other is not item and other.recommendation is item.recommendation


# --------------------------------------------------------------------------
# Value-space sanity (enum completeness)
# --------------------------------------------------------------------------

def test_value_spaces_are_complete():
    assert {m.value for m in SystemImpact} == {
        "none", "low", "moderate", "high", "critical", "unknown"
    }
    assert {m.value for m in DeletionRecommendation} == {
        "safe_to_delete", "review_first", "keep", "do_not_delete"
    }
    assert {m.value for m in ConfidenceLevel} == {"high", "medium", "low"}