"""Level 2/3 bounded-content classification (magic bytes; targeted <=4 KB).

Invoked ONLY via ``kb.classify_content(path, level=2|3)`` — never from the
live scanner (Phase 5 wiring). Both levels are bounded prefix reads:

- ``LEVEL2_MAX_BYTES = 512``  — Level 2 signature registry.
- ``LEVEL3_MAX_BYTES = 4096`` — Level 3 targeted confirmations.

There is deliberately NO "read the whole file" path anywhere in the KB.

Level 2 (<=512 B) — extension-independent magic-byte registry, resolving
ambiguous/extensionless types:

    SQLite    b"SQLite format 3\\x00"   -> databases
    PNG       b"\\x89PNG\\r\\n\\x1a\\n" -> media
    JPEG      b"\\xff\\xd8\\xff"        -> media
    GIF       b"GIF87a" / b"GIF89a"     -> media
    ZIP       b"PK\\x03\\x04"           -> archives  (zip/ooXML/jar/apk…)
    gzip      b"\\x1f\\x8b"             -> archives
    7zip      b"7z\\xbc\\xaf\\x27\\x1c" -> archives
    PDF       b"%PDF-"                  -> documents

Level 3 (<=4 KB) — rare, justified cases ONLY (documented; not a general
"deep inspect everything" path):

    1. SQLite header re-confirmation within the bounded window: if no signature
       appeared in the first 512 B but the full Level-3 window contains the
       SQLite magic (offset-wrapped containers), the file is ``databases``.
    2. Ollama manifest confirmation: only for paths whose components include
       ``ollama`` AND ``manifests``; read <=4 KB; if the leading JSON carries
       OCI-style manifest fields (``schemaVersion`` + ``mediaType``/``layers``)
       the verdict is ``app:ollama``.

Unknown stays unknown: no signature + no targeted match yields
``category="unknown"`` at every level — the KB never fabricates a positive
category from a low-confidence guess.
"""

from __future__ import annotations

import os
from typing import Optional

from ._norm import components, norm
from .result import KBResult

LEVEL2_MAX_BYTES = 512
LEVEL3_MAX_BYTES = 4096

# Longer/more specific signatures first to avoid prefix collisions.
_SIGNATURES: "tuple[tuple[bytes, str], ...]" = (
    (b"SQLite format 3\x00", "databases"),
    (b"\x89PNG\r\n\x1a\n", "media"),
    (b"\xff\xd8\xff", "media"),
    (b"GIF89a", "media"),
    (b"GIF87a", "media"),
    (b"7z\xbc\xaf\x27\x1c", "archives"),
    (b"PK\x03\x04", "archives"),
    (b"\x1f\x8b", "archives"),
    (b"%PDF-", "documents"),
)


def read_prefix(path: str, max_bytes: int) -> bytes:
    """Bounded prefix read. Never reads more than ``max_bytes`` bytes.

    Any open/read failure yields ``b""`` (never raises) so the KB degrades to
    ``unknown`` instead of crashing a scan.
    """
    try:
        with open(path, "rb") as handle:
            return handle.read(max_bytes)
    except OSError:
        return b""


def _is_ollama_manifest_path(key: str) -> bool:
    parts = components(key)
    return "ollama" in parts and "manifests" in parts


def classify_content(path: str, level: int = 2) -> KBResult:
    """Bounded-content classification at ``level`` (2 or 3)."""
    if level not in (2, 3):
        raise ValueError(f"level must be 2 or 3, got {level}")
    key = norm(path)
    limit = LEVEL3_MAX_BYTES if level == 3 else LEVEL2_MAX_BYTES
    prefix = read_prefix(path, limit)

    for signature, category in _SIGNATURES:
        if prefix.startswith(signature):
            return KBResult(path=key, category=category, confidence_hint="high",
                            level=level, detail=f"magic:{category}")

    if level >= 3:
        if b"SQLite format 3\x00" in prefix:
            return KBResult(path=key, category="databases",
                            confidence_hint="high", level=3,
                            detail="magic:sqlite:windowed")
        if _is_ollama_manifest_path(key):
            text = prefix.decode("utf-8", errors="ignore")
            if "schemaVersion" in text and (
                "mediaType" in text or "layers" in text
            ):
                return KBResult(path=key, category="app:ollama",
                                confidence_hint="high", level=3,
                                detail="magic:ollama:manifest")

    return KBResult(path=key, category="unknown", confidence_hint="low",
                    level=level)