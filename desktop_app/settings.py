"""Persisted desktop settings (Phase 10, S1-S2).

The UI language persists to a small JSON file under the user profile, using
only the stdlib (``json``/``pathlib``). Tests inject a temporary ``config_path``
so the real user file is never read or written during the suite.
"""

import json
import os
from pathlib import Path

_SUPPORTED_LANGS = ("en", "es")
_CONFIG_FILE_NAME = "folder-analyzer-desktop.json"


def default_config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "FolderAnalyzer" / _CONFIG_FILE_NAME


class AppSettings:
    def __init__(self, config_path: str | None = None):
        self._path = Path(config_path) if config_path else default_config_path()

    @property
    def path(self) -> Path:
        return self._path

    def load_language(self) -> str:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "en"
        lang = data.get("language", "en")
        return lang if lang in _SUPPORTED_LANGS else "en"

    def save_language(self, lang: str) -> None:
        if lang not in _SUPPORTED_LANGS:
            raise ValueError(f"unsupported language: {lang}")
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data["language"] = lang
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )