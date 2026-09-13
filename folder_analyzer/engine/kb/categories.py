"""Tiers 2 & 3 — common user/app data categories and extension categories.

Tier 2 (path patterns): browsers, dev tooling, AI/ML, games, Docker data,
caches/temp. Matching is against whole path *components* (casefolded), so a
file named ``notes.txt`` never trips a directory marker; only an actual
``cache``/``steam``/… directory name does.

Tier 3 (extensions): temp/cache, system, documents, media, archives,
databases, config — a curated, extensible table (material additions only, not
an exhaustive catalog of every extension in existence).

Dispatch interaction (first-match-wins, documented):
- Tier 2 is evaluated before Tier 3 (path evidence before extension evidence).
- App-specific anchors reserved for Tier 4 (Ollama/.docker, Python site-packages,
  Node node_modules, browser profile "user data") are deliberately ABSENT here so
  first-match-wins dispatch still reaches Tier 4.
- Under a known Tier-1 location the Tier-1 location category wins first; these
  tables classify paths outside known locations (auxiliary/external drives).

Both tables are module-level constants loaded once (memory/RSS discipline).
"""

from __future__ import annotations

import os
from typing import Optional

from ._norm import components, norm
from .result import KBResult

# Tier 2 — component-name pattern table (order matters: first match wins).
# Browser evidence precedes generic cache evidence so `Chrome\Cache` /
# `firefox\Cache2` classify as "browser" (the largest reclamation source),
# not the generic "cache" bucket.
_TIER2_PATTERNS: "tuple[tuple[str, frozenset[str]], ...]" = (
    ("browser", frozenset({
        "chrome", "chromium", "brave-browser", "brave", "opera", "vivaldi",
        "firefox", "mozilla", "microsoftedge", "safari",
    })),
    ("dev", frozenset({
        ".git", ".svn", ".hg", ".vscode", ".vs", ".terraform",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".m2",
    })),
    ("ai_ml", frozenset({
        "huggingface", "checkpoints", "weights", "gguf", "diffusers",
        "stable-diffusion", "comfyui", "invokeai", "automatic1111", "lora",
    })),
    ("game", frozenset({
        "steam", "steamapps", "steamcmd",
        "epic games", "battlenet", "blizzard", "riot games",
        "ea games", "ubisoft", "gog", "gog galaxy", "playnite",
    })),
    ("docker", frozenset({"docker", "containerd", "overlay2", "com.docker.service"})),
    ("cache", frozenset({"cache", "caches", ".cache", "temp", "tmp", "__pycache__", ".gradle"})),
)

# Union of all Tier-2 markers: single-set membership pass decides whether any
# path component hits at all; the group loop then only runs for matching paths
# (the overwhelmingly common no-match case pays one pass, not six).
_TIER2_MARKERS = frozenset(
    marker for _category, markers in _TIER2_PATTERNS for marker in markers
)

# Tier 3 — extension category table (lowercased, with leading dot).
_EXTENSIONS: "dict[str, str]" = {
    # -- temp/cache --
    ".tmp": "temp", ".temp": "temp", ".bak": "temp", ".old": "temp",
    ".dmp": "temp", ".log": "temp", ".cache": "temp", ".crdownload": "temp",
    ".part": "temp", ".download": "temp", ".lck": "temp",
    # -- system --
    ".sys": "system", ".dll": "system", ".drv": "system", ".ocx": "system",
    ".com": "system", ".scr": "system", ".cpl": "system", ".so": "system",
    ".mui": "system", ".ax": "system",
    # -- documents --
    ".txt": "documents", ".md": "documents", ".markdown": "documents",
    ".doc": "documents", ".docx": "documents", ".xls": "documents",
    ".xlsx": "documents", ".ppt": "documents", ".pptx": "documents",
    ".pdf": "documents", ".rtf": "documents", ".odt": "documents",
    ".ods": "documents", ".odp": "documents", ".csv": "documents",
    ".html": "documents", ".htm": "documents", ".epub": "documents",
    ".pages": "documents", ".numbers": "documents", ".key": "documents",
    ".tex": "documents",
    # -- media --
    ".jpg": "media", ".jpeg": "media", ".png": "media", ".gif": "media",
    ".bmp": "media", ".webp": "media", ".tif": "media", ".tiff": "media",
    ".svg": "media", ".ico": "media", ".heic": "media", ".avif": "media",
    ".mp3": "media", ".wav": "media", ".flac": "media", ".m4a": "media",
    ".ogg": "media", ".opus": "media", ".aac": "media", ".wma": "media",
    ".mid": "media", ".midi": "media",
    ".mp4": "media", ".mkv": "media", ".avi": "media", ".mov": "media",
    ".wmv": "media", ".webm": "media", ".flv": "media", ".m4v": "media",
    ".mpg": "media", ".mpeg": "media", ".3gp": "media", ".ogv": "media",
    # -- archives --
    ".zip": "archives", ".rar": "archives", ".7z": "archives",
    ".tar": "archives", ".gz": "archives", ".tgz": "archives",
    ".bz2": "archives", ".xz": "archives", ".zst": "archives",
    ".lz4": "archives", ".iso": "archives", ".cab": "archives",
    ".msi": "archives", ".msix": "archives", ".apk": "archives",
    ".dmg": "archives", ".deb": "archives", ".rpm": "archives",
    ".jar": "archives", ".war": "archives",
    # -- databases --
    ".db": "databases", ".db3": "databases", ".sqlite": "databases",
    ".sqlite3": "databases", ".sqlitedb": "databases", ".sql": "databases",
    ".mdb": "databases", ".accdb": "databases", ".dbf": "databases",
    ".mdf": "databases", ".ldf": "databases", ".ndf": "databases",
    # -- config --
    ".ini": "config", ".cfg": "config", ".conf": "config",
    ".config": "config", ".json": "config", ".yaml": "config",
    ".yml": "config", ".toml": "config", ".xml": "config",
    ".properties": "config", ".env": "config", ".reg": "config",
    ".editorconfig": "config", ".gitconfig": "config", ".cnf": "config",
    ".inf": "config", ".gitignore": "config",
}


def classify(path: str, *, _key: Optional[str] = None) -> Optional[KBResult]:
    """Tiers 2 then 3: component patterns before extension evidence."""
    key = _key if _key is not None else norm(path)
    parts = components(key)

    if any(part in _TIER2_MARKERS for part in parts):
        for category, markers in _TIER2_PATTERNS:
            if any(part in markers for part in parts):
                return KBResult(path=key, category=category, tier=2,
                                confidence_hint="medium",
                                detail="tier2:component")

    if not parts:
        return None
    ext = os.path.splitext(parts[-1])[1]
    category = _EXTENSIONS.get(ext)
    if category is not None:
        return KBResult(path=key, category=category, tier=3,
                        confidence_hint="high", detail="tier3:extension")
    return None