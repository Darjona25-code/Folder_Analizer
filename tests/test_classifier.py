"""Classifier tests (Phase 5): the KB->Assessment mapping table.

The invariants exercised here are the preconditions every other Phase 5
consumer trusts:

- floors I1/I3/I7/I9 are enforced at Assessment construction for every policy
  entry, so an unrepresentable SAFE_TO_DELETE cannot be built;
- the composition buckets are exhaustive and per-category (a known category is
  never accidentally degraded to UNKNOWN);
- the NOT_RESOLVABLE -> UNKNOWN pipeline (reason_key "not_resolvable",
  UNKNOWN impact, LOW confidence, at most REVIEW_FIRST);
- browser paths under an explicit disposable marker refine to DISPOSABLE.
"""

import os

import pytest

from folder_analyzer.engine.classifier import (
    CATEGORY_POLICY,
    ScanAssessment,
    _DISPOSABLE_MARKERS,
    assessment_from_scan_record,
    bucket_for_category,
    bucket_for_entry,
    classify_entry,
    classify_path,
    classify_scan,
)
from folder_analyzer.engine.enums import (
    CompositionBucket,
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from folder_analyzer.engine.kb import reset_session_caches
from folder_analyzer.engine.models import FileEntry


@pytest.fixture(autouse=True)
def _fresh_kb_session():
    reset_session_caches()
    yield
    reset_session_caches()


def _make_entry(path: str, size: int, assessment=None, category: str = "unknown") -> FileEntry:
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
        category=category,
    )


# ---------------------------------------------------------------------------
# Floor invariants across the whole policy table (I1/I3/I7/I9).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category",
    sorted(CATEGORY_POLICY),
)
def test_policy_entries_enforce_floor_invariants(category):
    path = f"C:\\fake\\{category}\\file.bin"
    assessment = classify_path(path)
    if assessment.detected_category == category:
        exp = CATEGORY_POLICY[category]
        assert assessment.recommendation is exp.recommendation
        assert assessment.confidence is exp.confidence
        assert assessment.impact is exp.impact
    # Floors: SAFE requires HIGH + non-UNKNOWN + no user data (construction
    # already mediates; this is a belt-and-braces re-checks).
    if assessment.recommendation is DeletionRecommendation.SAFE_TO_DELETE:
        assert assessment.confidence is ConfidenceLevel.HIGH
        assert assessment.impact is not SystemImpact.UNKNOWN
        assert assessment.is_user_data is False


@pytest.mark.parametrize(
    "category",
    sorted(CATEGORY_POLICY),
)
def test_known_categories_never_degrade_to_unknown_bucket(category):
    path = f"C:\\fake\\{category}\\file.bin"

    def _kb_category(path):
        from folder_analyzer.engine.kb import classify

        return classify(path).category

    # If the KB itself classifies this synthetic path, the classifier must
    # resolve that same category to a concrete (non-unknown) bucket.
    kb_cat = _kb_category(path)
    if kb_cat != "unknown":
        assert bucket_for_category(category, path) is not CompositionBucket.UNKNOWN


# ---------------------------------------------------------------------------
# Each bucket is reachable and carries the right aggregate shape.
# ---------------------------------------------------------------------------


def test_protected_bucket_is_do_not_delete_high():
    a = classify_path("C:\\Windows\\System32\\drivers\\foo.sys")
    assert a.detected_category == "system"
    assert a.recommendation is DeletionRecommendation.DO_NOT_DELETE
    assert a.confidence is ConfidenceLevel.HIGH
    p = CATEGORY_POLICY["system"]
    assert p.bucket is CompositionBucket.PROTECTED_CRITICAL
    assert p.impact is SystemImpact.CRITICAL
    assert bucket_for_category("system", "C:\\x") is CompositionBucket.PROTECTED_CRITICAL


def test_unknown_category_classifies_review_first_low_unknown_impact():
    a = classify_path("C:\\somewhere\\totally\\unmatched.bin")
    assert a.detected_category == "unknown"
    assert a.impact is SystemImpact.UNKNOWN
    assert a.confidence is ConfidenceLevel.LOW
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert bucket_for_category("unknown", "C:\\x") is CompositionBucket.UNKNOWN
    assert a.reason_key == "unknown_impact"


def test_disposable_positive_evidence_is_safe_and_high_and_temporary():
    a = classify_path("C:\\fake\\cache\\chrome_fast_cache.bin")
    assert a.detected_category == "cache"
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.confidence is ConfidenceLevel.HIGH
    assert a.impact is SystemImpact.NONE
    assert a.is_temporary is True
    assert a.reason_key == "disposable_positive_evidence"
    assert a.is_temporary is True
    assert bucket_for_category("cache", "C:\\fake\\cache\\file.bin") is CompositionBucket.DISPOSABLE


# ---------------------------------------------------------------------------
# Browser marker refinement.
# ---------------------------------------------------------------------------


def test_browser_under_marker_cache_directory_is_disposable():
    a = classify_path("C:\\Users\\me\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache\\f_000001")
    assert a.detected_category == "browser"
    assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert a.confidence is ConfidenceLevel.HIGH
    assert bucket_for_category(
        "browser",
        "C:\\Users\\me\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache\\f_000001",
    ) is CompositionBucket.DISPOSABLE


@pytest.mark.parametrize(
    "marker",
    sorted(_DISPOSABLE_MARKERS),
)
def test_browser_under_any_disposable_marker_is_disposable(marker):
    path = f"C:\\browser-app\\Chrome\\SomeBrand\\{marker}\\blob"
    assert bucket_for_category("browser", path) is CompositionBucket.DISPOSABLE


def test_browser_without_marker_stays_known_non_disposable():
    a = classify_path("C:\\browser-app\\Chrome\\User Data\\Default\\Preferences")
    assert a.detected_category == "browser"
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE
    assert a.confidence is ConfidenceLevel.MEDIUM
    assert bucket_for_category("browser", "C:\\browser-app\\Chrome\\User Data\\Default\\Preferences") \
        is CompositionBucket.KNOWN_NON_DISPOSABLE


def test_browser_category_mapping_direct():
    assert bucket_for_category("browser", "") is CompositionBucket.KNOWN_NON_DISPOSABLE
    assert bucket_for_category("browser", "C:\\x\\Chrome\\Cache\\f") is CompositionBucket.DISPOSABLE


# ---------------------------------------------------------------------------
# NOT_RESOLVABLE -> UNKNOWN pipeline (I1 case B).
# ---------------------------------------------------------------------------


def test_not_resolvable_classifies_as_unknown_review_low():
    a = classify_path("C:\\fake\\cache\\something.bin", not_resolvable=True)
    assert a.impact is SystemImpact.UNKNOWN
    assert a.confidence is ConfidenceLevel.LOW
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert a.reason_key == "not_resolvable"
    assert a.detected_category == "unknown"

    entry = _make_entry("C:\\fake\\cache\\something.bin", 123, assessment=a, category="unknown")
    assert bucket_for_entry(entry) is CompositionBucket.UNKNOWN


def test_not_resolvable_never_deletes_even_under_cache_parent():
    a = classify_path("C:\\temp\\x.bin", not_resolvable=True)
    assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
    entry = _make_entry("C:\\temp\\x.bin", 1, assessment=a, category="cache")
    assert bucket_for_entry(entry) is CompositionBucket.UNKNOWN


def test_not_resolvable_entry_buckets_unknown_by_reason_key():
    entry = _make_entry(
        "C:\\temp\\x.bin", 1,
        assessment=classify_path("C:\\temp\\x.bin", not_resolvable=True),
        category="cache",
    )
    assert bucket_for_entry(entry) is CompositionBucket.UNKNOWN


# ---------------------------------------------------------------------------
# Attribution: app_id descent and reason coherence.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "path", "expected_app_id"),
    [
        ("app:ollama", "C:\\users\\me\\.ollama\\models\\file.gguf", "ollama"),
        ("app:docker", "C:\\users\\me\\.docker\\daemon_cfg", "docker"),
        ("app:python", "C:\\proj\\.venv\\Scripts\\python.exe", "python"),
        ("app:node", "C:\\proj\\node_modules\\lodash\\index.js", "node"),
        # Tier-4 browser-profile rule fires WITHOUT a brand marker ("profiles").
        ("app:browser", "C:\\dev\\backup\\profiles\\user data\\something", "browser"),
    ],
)
def test_app_id_attribution(category, path, expected_app_id):
    a = classify_path(path)
    assert a.detected_category == category
    assert a.app_id == expected_app_id
    assert a.reason_key == "known_non_disposable"
    assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE


def test_app_category_policy_is_high_impact_review_medium():
    # ``category == "app"`` (Tier 5 registry wildcard) has no forced path
    # fixture; assert its policy mapping directly.
    p = CATEGORY_POLICY["app"]
    assert p.bucket is CompositionBucket.KNOWN_NON_DISPOSABLE
    assert p.impact is SystemImpact.HIGH
    assert p.confidence is ConfidenceLevel.MEDIUM
    assert p.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert bucket_for_category("app", "C:\\x") is CompositionBucket.KNOWN_NON_DISPOSABLE


def test_user_value_categories_never_safe_and_flag_user_data():
    for path in (
        "C:\\fake\\documents\\report.docx",
        "C:\\fake\\media\\photo.jpg",
        "C:\\fake\\archives\\backup.zip",
        "C:\\fake\\databases\\app.db",
    ):
        a = classify_path(path)
        assert a.is_user_data is True
        assert a.recommendation is DeletionRecommendation.REVIEW_FIRST
        assert a.confidence is ConfidenceLevel.HIGH
        assert bucket_for_category(a.detected_category, path) is CompositionBucket.USER_VALUE


def test_location_driven_user_value_and_app_data(monkeypatch):
    """downloads/desktop/user_profile/app_data are location-driven (Tier 1),
    resolved from env + Known Folders once per session. Pin them deterministically."""
    monkeypatch.setenv("USERPROFILE", "C:\\fake\\home")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\fake\\localappdata")
    monkeypatch.setenv("APPDATA", "C:\\fake\\roamingappdata")
    monkeypatch.setenv("TEMP", "C:\\fake\\temp")
    monkeypatch.setenv("TMP", "C:\\fake\\temp")

    import folder_analyzer.engine.kb.env_paths as env_paths

    orig_lookup = env_paths._known_folder_path

    def fake_known_folder(_key):
        return "C:\\fake\\downloads"

    env_paths._known_folder_path = fake_known_folder
    try:
        reset_session_caches()
        cases = {
            "C:\\fake\\downloads\\setup.exe": "downloads",
            "C:\\fake\\temp\\x.tmp": "temp",
            "C:\\fake\\localappdata\\Store\\settings.json": "app_data_local",
            "C:\\fake\\roamingappdata\\App\\prefs.json": "app_data_roaming",
            "C:\\fake\\home\\.bashrc": "user_profile",
        }
        for path, expected in cases.items():
            a = classify_path(path)
            assert a.detected_category == expected, path
            if expected == "temp":
                assert a.recommendation is DeletionRecommendation.SAFE_TO_DELETE
                assert a.is_temporary is True
            else:
                assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE
            if expected in ("downloads", "user_profile"):
                assert a.is_user_data is True
                assert bucket_for_category(expected, path) is CompositionBucket.USER_VALUE
            elif expected == "temp":
                assert bucket_for_category(expected, path) is CompositionBucket.DISPOSABLE
            else:
                assert bucket_for_category(expected, path) \
                    is CompositionBucket.KNOWN_NON_DISPOSABLE
    finally:
        env_paths._known_folder_path = orig_lookup
        reset_session_caches()


def test_config_and_dev_are_known_non_disposable_never_safe():
    for path in (
        "C:\\fake\\config\\weird.conf",
        "C:\\proj\\.vscode\\settings.json",
        "C:\\models\\huggingface\\weights.bin",
        "C:\\games\\steamapps\\common\\game\\config.ini",
        "C:\\docker\\containerd\\data.db",
    ):
        a = classify_path(path)
        assert a.recommendation is not DeletionRecommendation.SAFE_TO_DELETE
        assert bucket_for_category(a.detected_category, path) \
            is CompositionBucket.KNOWN_NON_DISPOSABLE


def test_scan_record_materializes_identical_assessment():
    """The allocation-lean scan record is the full Assessment by construction:
    materializing yields the exact same verdict across every policy path."""
    paths = (
        "C:\\Windows\\System32\\ntdll.dll",
        "C:\\ProgramData\\app\\settings.ini",
        "C:\\Users\\me\\Downloads\\installer.exe",
        "C:\\Users\\me\\Documents\\notes.txt",
        "C:\\dev\\backup\\profiles\\user data\\something.sqlite",
        "C:\\Chrome\\Cache\\f_0001",
        "C:\\Chrome\\Cache2\\f_0002",
        "C:\\firefox\\profile\\Cache\\f_0003",
        "C:\\odd\\unknown_extension.dat_zz",
        "C:\\src\\project\\.vscode\\settings.json",
        "C:\\data\\file.docx",
        "C:\\games\\steamapps\\common\\game\\config.ini",
    )
    for path in paths:
        rec = classify_scan(path)
        assert isinstance(rec, ScanAssessment)
        full = classify_path(path)
        materialized = assessment_from_scan_record(rec)
        assert materialized.impact is full.impact
        assert materialized.confidence is full.confidence
        assert materialized.reason_key == full.reason_key
        assert materialized.recommendation is full.recommendation
        assert materialized.reason_params == full.reason_params
        assert materialized.detected_category == full.detected_category
        assert materialized.app_id == full.app_id
        assert materialized.is_user_data is full.is_user_data
        assert materialized.is_temporary is full.is_temporary
        # Bucket carried by the record matches the path-aware bucket mapping.
        assert rec.bucket is bucket_for_category(rec.detected_category or "unknown", path)


def test_scan_record_not_resolvable_pipeline_materializes():
    rec = classify_scan("C:\\resolver\\mystery.bin", not_resolvable=True)
    assert rec.bucket is CompositionBucket.UNKNOWN
    full = assessment_from_scan_record(rec)
    assert full.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert full.impact is SystemImpact.UNKNOWN
    assert full.confidence is ConfidenceLevel.LOW
    assert full.reason_key == "not_resolvable"
    assert full.detected_category == "unknown"