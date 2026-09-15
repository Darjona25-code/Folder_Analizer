"""Phase 7 — single-source locale migration guarantees.

The locale files are the single source of truth for BOTH ui strings and the
reason_key registry. These tests enforce:
  * file shape (``{"ui": ..., "reasons": ...}``, all str values),
  * EN/ES key parity per namespace (a key existing in one locale must exist in
    the other),
  * the Python modules read exactly the same files (“no duplicated strings”),
  * every reason_key from the Phase 6 registry audit (``tests.test_explain``)
    is present and resolves to real, non-raw localized text.
"""

import json
from pathlib import Path

from folder_analyzer.engine.explain import resolve_reason
from folder_analyzer.i18n import REASONS, STRINGS
from tests.test_explain import KNOWN_KEYS

LOCALES_DIR = Path(__file__).resolve().parents[1] / "folder_analyzer" / "locales"
LANGS = ("en", "es")


def _load(lang: str) -> dict:
    with open(LOCALES_DIR / f"{lang}.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_locale_files_exist_and_have_expected_shape():
    for lang in LANGS:
        data = _load(lang)
        assert set(data) == {"ui", "reasons"}, f"{lang}.json must have ui+reasons"
        assert all(isinstance(v, str) for v in data["ui"].values())
        assert all(isinstance(v, str) for v in data["reasons"].values())


def test_en_es_key_parity_per_namespace():
    en, es = _load("en"), _load("es")
    assert set(en["ui"]) == set(es["ui"]), "a ui key exists in one locfile only"
    assert set(en["reasons"]) == set(es["reasons"])


def test_python_modules_read_the_same_single_source():
    en = _load("en")
    assert STRINGS["en"] == en["ui"]
    assert REASONS["en"] == en["reasons"]
    assert STRINGS["es"] == _load("es")["ui"]
    assert REASONS["es"] == _load("es")["reasons"]


def test_all_registered_reason_keys_present_and_non_raw():
    en = _load("en")
    assert set(en["reasons"]) == set(KNOWN_KEYS)
    for key in KNOWN_KEYS:
        assert key in en["reasons"]
        for lang in LANGS:
            resolved = resolve_reason(key, lang=lang)
            assert resolved != key, f"reason {key!r} resolves to raw in {lang}"
            assert resolved.strip()