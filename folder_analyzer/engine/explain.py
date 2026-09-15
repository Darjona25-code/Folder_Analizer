"""Explainability foundation — localized resolution of ``reason_key`` strings (Phase 2).

Resolves reason keys produced by the safety/classification/composition space.
The per-language reason registry is single-source and lives in
``folder_analyzer/locales/{lang}.json`` (the ``reasons`` section), shared with
the UI strings and served to the Web UI via ``GET /api/i18n``; the Python side
only re-exports it from ``folder_analyzer.i18n``.
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..i18n import REASONS  # noqa: F401  (single source, re-exported for callers)


def resolve_reason(
    reason_key: str,
    lang: str = "en",
    params: Optional[Mapping[str, object]] = None,
) -> str:
    """Resolve a reason_key into localized, interpolated text.

    Unknown keys return the key itself (same fallback behavior as i18n.py).
    """
    text = REASONS.get(lang, REASONS["en"]).get(reason_key, reason_key)
    if params:
        return text.format(**params)
    return text