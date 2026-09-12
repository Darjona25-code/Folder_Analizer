"""Tier 4 — high-value application rules (material additions, not a catalog).

Implemented app anchors (each deliberately does NOT overlap Tier 2 markers so
the first-match-wins dispatch reaches Tier 4 for them):

- Ollama: components ``ollama`` / ``.ollama`` (model store; the manifest
  check in ``content.py`` provides the Level 3 confirmation).
- Docker: ``.docker`` config dir, ``com.docker``/``com.docker.service``
  app-data markers (generic ``docker``/``overlay2`` data dirs are Tier 2).
- Python: ``site-packages``, ``dist-packages``, ``.venv``, ``venv``,
  ``virtualenvs``, ``pyvenv.cfg``.
- Node.js: ``node_modules``, ``.npm``, ``.yarn``, ``.pnpm-store``, ``_cacache``.
- Browser profiles: ``user data`` (Chrome/Edge), ``profiles``, ``.mozilla``
  (Firefox) — Tier 2's brand markers catch normal browser dirs first; this
  rule covers profile dirs Tier 2 does not.

All marker sets are module-level constants loaded once (memory discipline).
"""

from __future__ import annotations

from typing import Optional

from ._norm import components, norm
from .result import KBResult

_TIER4_PATTERNS: "tuple[tuple[str, frozenset[str]], ...]" = (
    ("app:ollama", frozenset({"ollama", ".ollama"})),
    ("app:docker", frozenset({".docker", "com.docker", "com.docker.service"})),
    ("app:python", frozenset({
        "site-packages", "dist-packages", ".venv", "venv", "virtualenvs",
        "pyvenv.cfg",
    })),
    ("app:node", frozenset({
        "node_modules", ".npm", ".yarn", ".pnpm-store", "_cacache",
    })),
    ("app:browser", frozenset({"user data", "profiles", ".mozilla"})),
)


def classify(path: str) -> Optional[KBResult]:
    key = norm(path)
    parts = components(key)
    for category, markers in _TIER4_PATTERNS:
        if any(part in markers for part in parts):
            return KBResult(path=key, category=category, tier=4,
                            confidence_hint="medium", detail="tier4:component")
    return None