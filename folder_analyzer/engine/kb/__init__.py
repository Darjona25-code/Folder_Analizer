"""Knowledge Base package (Phase 4, roadmap §10).

Categories-only layer. Public entry points:

- ``classify(path)`` — tiered dispatch 0 -> 5; first match wins; when nothing
  matches the verdict is ``category="unknown"`` (never a forced guess).
- ``classify_content(path, level=2|3)`` — bounded content analysis for
  ambiguous file types (Level 2 magic bytes <=512 B; Level 3 targeted <=4 KB).
- ``reset_session_caches()`` — clears per-scan-session caches (env/Known
  Folder resolution + registry batch-load) at scan boundaries and in tests.

Design choice (documented): the dispatch loop lives in this package's
``__init__`` rather than a separate ``kb_dispatcher`` module — it is the
package's one public entry contract (~20 lines) and avoids a layer of
indirection; each tier module stays independently importable, satisfying the
Phase 4 integration boundary that tests exercise modules in isolation.

Integration boundary: the KB produces ``KBResult`` verdicts only. It never
constructs ``Assessment`` objects and is never imported by the live scanner's
scan path; ``classifier.py``/``recommender.py`` wiring is Phase 5.
"""

from __future__ import annotations

import os

from .result import KBResult

__all__ = ["KBResult", "classify", "classify_content", "reset_session_caches"]


def _classify_tier(module, path: str):
    return module.classify(path)


_TIERS = (
    (0, "known_paths"),
    (1, "env_paths"),
    (2, "categories"),  # tiers 2 (patterns) then 3 (extensions), same module
    (4, "apps"),
    (5, "registry"),
)


def classify(path: str) -> KBResult:
    """Tiered dispatch: Tier 0 -> 5, first match wins, else ``unknown``."""
    from . import apps, categories, env_paths, known_paths, registry

    _modules = {
        "known_paths": known_paths,
        "env_paths": env_paths,
        "categories": categories,
        "apps": apps,
        "registry": registry,
    }
    for _tier, module_name in _TIERS:
        result = _modules[module_name].classify(path)
        if result is not None:
            return result
    return KBResult(
        path=os.path.normcase(os.path.normpath(path)),
        category="unknown",
        confidence_hint="low",
    )


def classify_content(path: str, level: int = 2) -> KBResult:
    """Bounded-content classification (Level 2 magic bytes / Level 3 targeted)."""
    from .content import classify_content as _content

    return _content(path, level=level)


def reset_session_caches() -> None:
    """Clear per-scan-session caches (env/Known Folders + registry)."""
    from . import env_paths, registry

    env_paths.reset_cache()
    registry.reset_cache()