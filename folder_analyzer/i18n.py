"""Bilingual support (EN/ES) for Folder Analyzer.

Single source of truth: ``folder_analyzer/locales/{lang}.json`` — each file
carries two namespaces, ``ui`` (application strings, ex-CLI/export/API) and
``reasons`` (the explainability reason_key registry, ex-``explain.REASONS``).
CLI, API, exporters, and the Web UI (via ``GET /api/i18n``) all read from the
same two files; no translation string lives in a Python dict.
"""

import json
from pathlib import Path
from typing import Dict

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_LANGS = ("en", "es")


def load_locales() -> Dict[str, dict]:
    """Load every ``locales/{lang}.json`` file once, at import time."""
    locales: Dict[str, dict] = {}
    for lang in _LANGS:
        path = _LOCALES_DIR / f"{lang}.json"
        with open(path, encoding="utf-8") as fh:
            locales[lang] = json.load(fh)
    return locales


_LOCALES = load_locales()

# Both namespaces are single-source (no string duplication in Python). The
# ``en``/``es`` key sets are equal by construction (parity-tested in
# ``tests/test_locales.py``).
STRINGS: Dict[str, Dict[str, str]] = {
    lang: data["ui"] for lang, data in _LOCALES.items()
}
REASONS: Dict[str, Dict[str, str]] = {
    lang: data["reasons"] for lang, data in _LOCALES.items()
}


class I18n:
    def __init__(self, lang: str = "en"):
        if lang not in STRINGS:
            lang = "en"
        self.lang = lang

    def t(self, key: str, **kwargs) -> str:
        text = STRINGS.get(self.lang, STRINGS["en"]).get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text

    def set_lang(self, lang: str):
        if lang in STRINGS:
            self.lang = lang