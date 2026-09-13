"""Explainability foundation tests (Phase 2): reason_key localization."""

import pytest

from folder_analyzer.engine.explain import REASONS, resolve_reason

KNOWN_KEYS = [
    "unknown_impact",
    "confidence_gate_promoted",
    "confidence_low",
    "user_data",
    "temporary_data",
    "clean_system_data",
    "review_before_delete",
    "keep",
    "do_not_delete",
    # Phase 5 item-level classification reasons (classifier.py).
    "protected_critical",
    "disposable_positive_evidence",
    "user_value",
    "known_non_disposable",
    "not_resolvable",
    # Phase 5 folder-level composition reasons (recommender.py).
    "r1_protected_critical",
    "r2_user_value",
    "downloads_policy",
    "r3_unknown",
    "r4_known_non_disposable_share",
    "r5_safe_to_delete",
    "r6_review_first",
]


def test_both_locales_cover_all_keys():
    assert set(REASONS["en"]) == set(REASONS["es"]) == set(KNOWN_KEYS)


def test_all_keys_resolve_in_both_locales():
    for lang in ("en", "es"):
        for key in KNOWN_KEYS:
            text = resolve_reason(key, lang=lang)
            assert text != key  # resolved, not fallback
            assert text.strip()


def test_unknown_key_falls_back_to_key():
    assert resolve_reason("no_such_reason", lang="en") == "no_such_reason"


def test_params_interpolated():
    text = resolve_reason("confidence_gate_promoted", lang="en",
                          params={"confidence": "Medium"})
    assert "Medium" in text
    assert "{confidence}" not in text


def test_es_resolves():
    assert "confianza" in resolve_reason("confidence_low", lang="es")