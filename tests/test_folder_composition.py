"""Folder composition tests (Phase 5): compose() aggregation + invariants,
and the seven canonical roadmap §11 composition examples end-to-end
(classification -> compose -> derive_folder_recommendation).

Canonical examples are numbered as in docs/ROADMAP.md §11:
1, 2, 3, 4, 5, 6, 8. (Example 7 `C:\\Users` is a protected-policy case driven
by I6/I7, not composition-deterministic, so it is asserted via the R1 hard
rule in test_recommender.py rather than here.)
"""

import os

import pytest

from folder_analyzer.engine.classifier import classify_path
from folder_analyzer.engine.enums import (
    CompositionBucket,
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from folder_analyzer.engine.kb import reset_session_caches
from folder_analyzer.engine.models import Assessment, FileEntry
from folder_analyzer.engine.recommender import (
    compose,
    derive_folder_recommendation,
    CompositionConfig,
)

_SYSTEM_ROOT = os.environ.get("SystemRoot", "C:\\Windows")


@pytest.fixture(autouse=True)
def _fresh_kb_session():
    reset_session_caches()
    yield
    reset_session_caches()


def _entry(path: str, size: int, assessment: Assessment) -> FileEntry:
    name = os.path.basename(path)
    _, ext = os.path.splitext(name)
    return FileEntry(
        path=path,
        filename=name,
        extension=ext.lower(),
        size=size,
        created_ts=1.0,
        modified_ts=1.0,
        accessed_ts=1.0,
        attributes={"st_mode": 0, "st_ino": 1, "st_nlink": 1, "is_symlink": False},
        assessment=assessment,
        category=(assessment.detected_category or "unknown"),
    )


def _classified(path: str, size: int) -> FileEntry:
    return _entry(path, size, classify_path(path))


# ---------------------------------------------------------------------------
# compose() aggregation invariants.
# ---------------------------------------------------------------------------


def test_compose_buckets_are_exhaustive_byte_sum_invariant():
    entries = [
        _classified("C:\\fake\\cache\\f1_cache.bin", 10),
        _classified(_SYSTEM_ROOT + "\\System32\\drivers\\f2.sys", 20),
        _classified("C:\\fake\\docs\\report.docx", 30),
        _classified("C:\\fake\\unknown_file.xyz", 40),
        _classified("C:\\fake\\config\\settings.json", 50),
    ]
    comp = compose(entries)
    bucket_sum = sum(comp.buckets.values())
    assert bucket_sum == comp.total_bytes == 10 + 20 + 30 + 40 + 50
    assert sum(comp.by_category.values()) == comp.total_bytes
    shares = sum(comp.share(b) for b in CompositionBucket)
    assert shares == pytest.approx(1.0)
    assert comp.share(CompositionBucket.DISPOSABLE) == pytest.approx(10 / 150)
    assert comp.share(CompositionBucket.PROTECTED_CRITICAL) == pytest.approx(20 / 150)
    assert comp.share(CompositionBucket.USER_VALUE) == pytest.approx(30 / 150)
    assert comp.share(CompositionBucket.KNOWN_NON_DISPOSABLE) == pytest.approx(50 / 150)
    assert comp.share(CompositionBucket.UNKNOWN) == pytest.approx(40 / 150)


def test_compose_zero_byte_entries_carry_bucket_but_no_bytes():
    zero = _classified("C:\\fake\\cache\\empty_cache.bin", 0)
    big = _classified("C:\\fake\\cache\\big_cache.bin", 100)
    comp = compose([zero, big])
    assert comp.total_bytes == 100
    assert comp.share(CompositionBucket.DISPOSABLE) == pytest.approx(1.0)
    assert comp.disposable_bytes == 100


def test_compose_by_category_tracks_raw_categories():
    entries = [
        _classified("C:\\fake\\cache\\a.bin", 10),
        _classified("C:\\fake\\media\\photo.jpg", 20),
    ]
    comp = compose(entries)
    assert comp.by_category == {"cache": 10, "media": 20}
    assert comp.disposable_bytes == 10
    assert comp.user_value_bytes == 20


def test_compose_explicit_total_bytes_parameter():
    entries = [_classified("C:\\fake\\cache\\a.bin", 5)]
    comp = compose(entries, total_bytes=100)
    assert comp.total_bytes == 100
    assert comp.disposable_bytes == 5
    assert comp.share(CompositionBucket.DISPOSABLE) == pytest.approx(0.05)


def test_compose_not_resolvable_aggregates_unknown_bucket():
    nr = _classified("C:\\fake\\cache\\f.bin", 30)
    # Override with the NOT_RESOLVABLE pipeline verdict (Case B).
    nr = _entry("C:\\fake\\cache\\f.bin", 30,
                classify_path("C:\\fake\\cache\\f.bin", not_resolvable=True))
    disposable = _classified("C:\\fake\\cache\\g.bin", 570)
    comp = compose([disposable, nr])

    assert comp.unknown_bytes == 30
    assert comp.not_resolvable_count == 1
    assert comp.share(CompositionBucket.DISPOSABLE) == pytest.approx(0.95)
    assert comp.share(CompositionBucket.UNKNOWN) == pytest.approx(0.05)

    folder = derive_folder_recommendation(None, comp)
    # 95% disposable + 5% UNKNOWN -> R3 (exactly canonical example 4 shape).
    assert folder.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert folder.reason_key == "r3_unknown"


# ---------------------------------------------------------------------------
# Canonical roadmap examples (7 of them; ex7 is I6-policy territory).
# ---------------------------------------------------------------------------

CANONICALS = [
    (
        "ex1_pure_disposable_cache",
        [
            _classified("C:\\fake\\cache\\cache_a.bin", 100),
            _classified("C:\\fake\\cache\\cache_b.bin", 100),
        ],
        SystemImpact.NONE,
        DeletionRecommendation.SAFE_TO_DELETE,
        ConfidenceLevel.HIGH,
        "r5_safe_to_delete",
    ),
    (
        "ex2_pure_critical_system",
        [
            _classified(_SYSTEM_ROOT + "\\System32\\drivers\\sys_a.sys", 100),
            _classified(_SYSTEM_ROOT + "\\System32\\drivers\\sys_b.sys", 100),
        ],
        SystemImpact.CRITICAL,
        DeletionRecommendation.DO_NOT_DELETE,
        ConfidenceLevel.HIGH,
        "r1_protected_critical",
    ),
    (
        "ex3_mixed_disposable_critical",
        [
            _classified("C:\\fake\\cache\\cache_a.bin", 100),
            _classified(_SYSTEM_ROOT + "\\System32\\drivers\\sys_a.sys", 100),
        ],
        SystemImpact.HIGH,
        DeletionRecommendation.DO_NOT_DELETE,
        ConfidenceLevel.HIGH,
        "r1_protected_critical",
    ),
    (
        "ex4_95_disposable_5_unknown",
        [
            _classified("C:\\fake\\cache\\cache_a.bin", 190),
            _classified("C:\\fake\\mystery.qux", 10),
        ],
        SystemImpact.LOW,
        DeletionRecommendation.REVIEW_FIRST,
        ConfidenceLevel.MEDIUM,
        "r3_unknown",
    ),
    (
        "ex5_60_cache_40_unknown",
        [
            _classified("C:\\fake\\cache\\cache_a.bin", 60),
            _classified("C:\\fake\\mystery.qux", 40),
        ],
        SystemImpact.UNKNOWN,
        DeletionRecommendation.REVIEW_FIRST,
        ConfidenceLevel.LOW,
        "r3_unknown",
    ),
    (
        "ex6_personal_docs_app_data",
        [
            _classified("C:\\fake\\docs\\report.docx", 100),
            _classified("C:\\fake\\config\\settings.json", 100),
        ],
        SystemImpact.NONE,
        DeletionRecommendation.REVIEW_FIRST,
        ConfidenceLevel.HIGH,
        "r2_user_value",
    ),
    (
        "ex8_downloads_policy",
        [
            _entry(
                "C:\\fake\\downloads\\setup.exe",
                100,
                Assessment(
                    impact=SystemImpact.LOW,
                    confidence=ConfidenceLevel.HIGH,
                    reason_key="user_value",
                    recommendation=DeletionRecommendation.REVIEW_FIRST,
                    detected_category="downloads",
                    is_user_data=True,
                ),
            ),
        ],
        SystemImpact.LOW,
        DeletionRecommendation.REVIEW_FIRST,
        ConfidenceLevel.HIGH,
        "downloads_policy",
    ),
]


@pytest.mark.parametrize(
    ("name", "entries", "exp_impact", "exp_rec", "exp_conf", "exp_reason"),
    CANONICALS,
    ids=[c[0] for c in CANONICALS],
)
def test_canonical_composition_example(
    name, entries, exp_impact, exp_rec, exp_conf, exp_reason,
):
    comp = compose(entries)
    assert comp.total_bytes == sum(e.size for e in entries)
    folder = derive_folder_recommendation(None, comp)
    assert folder.impact is exp_impact, name
    assert folder.recommendation is exp_rec, name
    assert folder.confidence is exp_conf, name
    assert folder.reason_key == exp_reason, name


def test_canonical_ex4_matches_user_corrected_expectation():
    """User-corrected Example 4: 95% disposable + 5% UNKNOWN must be
    LOW/REVIEW_FIRST/MEDIUM (R3 UNKNOWN_BLOCK = 0.0), NOT SAFE."""
    comp = compose([
        _classified("C:\\fake\\cache\\cache_a.bin", 190),
        _classified("C:\\fake\\mystery.qux", 10),
    ])
    folder = derive_folder_recommendation(None, comp)
    assert folder.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert folder.impact is SystemImpact.LOW
    assert folder.confidence is ConfidenceLevel.MEDIUM
    assert folder.reason_key == "r3_unknown"


def test_folder_confidence_gate_demotes_r5_eligible_safe_to_review():
    """Isolated I9 at FOLDER level (reviewer REQUIRED this directly).

    Build a composition that satisfies R5's share gates exactly (disposable
    0.90, known_non_disposable 0.10, zero UNKNOWN bytes — so R1/R2/R3/R4
    cannot fire: PROTECTED_CRITICAL=0, USER_VALUE=0, UNKNOWN=0, known_share
    0.10 < REVIEW_SHARE 0.15). At the default gate this is SAFE_TO_DELETE/HIGH.
    When the folder's classification evidence is genuinely credible only to
    MEDIUM or LOW confidence (gate lowered), the construction-time confidence
    gate I9 must demote the folder to REVIEW_FIRST — proving the folder-level
    gate fires and that no SAFE rationale survives the demotion.
    """
    entries = [
        _classified("C:\\fake\\cache\\cache_a.bin", 900),
        _classified("C:\\fake\\config\\settings.json", 100),
    ]
    comp = compose(entries)
    assert comp.share(CompositionBucket.DISPOSABLE) == pytest.approx(0.9)
    assert comp.share(CompositionBucket.KNOWN_NON_DISPOSABLE) == pytest.approx(0.1)
    assert comp.protected_critical_bytes == 0
    assert comp.user_value_bytes == 0
    assert comp.unknown_bytes == 0  # R3 is NOT the gating rule here

    default = derive_folder_recommendation(None, comp)
    assert default.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert default.confidence is ConfidenceLevel.HIGH
    assert default.reason_key == "r5_safe_to_delete"

    for gate in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW):
        folder = derive_folder_recommendation(
            None, comp, config=CompositionConfig(confidence_gate=gate))
        assert folder.recommendation is DeletionRecommendation.REVIEW_FIRST
        assert folder.confidence is gate
        assert folder.reason_key == "confidence_gate_promoted"


def test_folder_safe_never_carries_below_high_confidence_under_default_gate():
    """Exhaustive I9 well-formedness across the R5-eligible share band.

    Under the default configuration the pipeline can never emit a SAFE folder
    with confidence below HIGH; genuinely uncertain evidence is expressed only
    through the share ladder (UNKNOWN -> R3, KNOWN_NON_DISPOSABLE -> R4/R6),
    so an ``Assessment`` constructed by ``derive_folder_recommendation`` always
    satisfies I9 at the source.
    """
    config = CompositionConfig()
    for known_share in (0.0, 0.05, 0.10):
        entries = [
            _classified("C:\\fake\\cache\\cache_a.bin",
                        int((1 - known_share) * 1000)),
            _classified("C:\\fake\\config\\settings.json",
                        int(known_share * 1000)),
        ]
        folder = derive_folder_recommendation(None, compose(entries), config=config)
        if folder.recommendation is DeletionRecommendation.SAFE_TO_DELETE:
            assert folder.confidence is ConfidenceLevel.HIGH


def test_canonical_folder_assessments_resolve_in_both_locales():
    from folder_analyzer.engine.explain import resolve_reason

    for name, entries, _, _, _, reason in CANONICALS:
        comp = compose(entries)
        folder = derive_folder_recommendation(None, comp)
        assert folder.reason_key == reason
        for lang in ("en", "es"):
            text = resolve_reason(folder.reason_key, lang=lang,
                                  params=folder.reason_params)
            assert text != folder.reason_key
            assert text.strip()