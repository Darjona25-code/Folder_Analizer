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
constructs ``Assessment`` objects and never performs file I/O. The scan hot
path reuses a per-folder ``ScanFolderContext`` (``prepare_scan_folder`` /
``classify_scan_path``) so the folder-transitive tiers run once per folder
while staying byte-identical to ``kb.classify``; ``classifier.py`` wiring is
Phase 5.
"""

from __future__ import annotations

import os
from typing import Optional

from ._norm import components, norm
from .result import KBResult

__all__ = [
    "KBResult",
    "classify",
    "classify_content",
    "reset_session_caches",
    "ScanFolderContext",
    "prepare_scan_folder",
    "classify_scan_path",
]


def _classify_tier(module, path: str):
    return module.classify(path)


_TIERS = (
    (0, "known_paths"),
    (1, "env_paths"),
    (2, "categories"),  # tiers 2 (patterns) then 3 (extensions), same module
    (4, "apps"),
    (5, "registry"),
)

_TIER_MODULES = None


def _tier_modules():
    """Lazy once-per-process module map (never rebuilt per classification
    call — the 50k-file scan path classifies every file)."""
    global _TIER_MODULES
    if _TIER_MODULES is None:
        from . import apps, categories, env_paths, known_paths, registry

        _TIER_MODULES = {
            "known_paths": known_paths,
            "env_paths": env_paths,
            "categories": categories,
            "apps": apps,
            "registry": registry,
        }
    return _TIER_MODULES


def classify(path: str, *, _key: Optional[str] = None) -> KBResult:
    """Tiered dispatch: Tier 0 -> 5, first match wins, else ``unknown``.

    ``_key`` is the pre-normalized path (kb owns the single normalization when
    it is the caller's entry point); direct tier test callers omit it.
    """
    key = _key if _key is not None else os.path.normcase(os.path.normpath(path))
    for _tier, module_name in _TIERS:
        result = _tier_modules()[module_name].classify(path, _key=key)
        if result is not None:
            return result
    return KBResult(path=key, category="unknown", confidence_hint="low")


_MISS = object()

# Bounded per-folder filename verdict cache (Phase 8 fast path). Tiers 2/3/4
# verdicts depend only on the folder parts plus the file name, so within one
# ``ScanFolderContext`` repeated names can reuse the resolved tier-2/3/4
# KBResult instead of re-running the marker/extension tables per file. Capped
# so huge single folders never grow an unbounded dict; the registry fallback
# (tier 5) is deliberately NOT cached (it re-tests the file path each call,
# keeping its per-file semantics exact).
_NAME_CACHE_CAP = 256


class ScanFolderContext:
    """Per-folder pre-resolved dispatch state for the scan hot path.

    Built once per scanned folder (``prepare_scan_folder``) and passed to
    ``classify_scan_path`` for every file beneath it. Per-file equality with
    ``kb.classify`` is exact: tiers 0/1/5 match a path iff the path descends
    within a known root, so a folder's verdict (or miss) is decided here once
    and never re-tested per file. Component tiers 2/4 and the extension tier 3
    still run per file against ``folder_parts`` plus the file name, so a file
    that contributes its own marker or extension changes the verdict exactly
    as standalone classification would.
    """

    __slots__ = ("folder_key", "folder_parts", "t0_tree", "t0_exact", "t1", "t5",
                 "t2_scan", "t4_scan", "name_cache")

    def __init__(self, folder_key, folder_parts, t0_tree, t0_exact, t1, t5,
                 t2_scan=False, t4_scan=False, name_cache=None) -> None:
        self.folder_key = folder_key
        self.folder_parts = folder_parts
        self.t0_tree = t0_tree
        self.t0_exact = t0_exact
        self.t1 = t1
        self.t5 = t5
        self.t2_scan = t2_scan
        self.t4_scan = t4_scan
        self.name_cache = name_cache


def prepare_scan_folder(folder_path: str) -> ScanFolderContext:
    """Resolve the folder-transitive tiers (0/1/5) for one scanned folder.

    ``t0_tree`` is the Tier-0 *tree* verdict (inherited by every file beneath);
    ``t0_exact`` records that the folder is itself an exact root and so its
    files are deliberately NOT Tier-0 (drive() roots are critical, descendants
    are not). ``t1``/``t5`` are the folder's env/registry verdicts, both
    prefix-transitive (an EXACT``==`` hit on a non-dir path is impossible for a
    folder). Component/extension tiers are deliberately NOT pre-resolved.
    """
    modules = _tier_modules()
    key = norm(folder_path)
    parts = tuple(components(key))
    t0 = modules["known_paths"].classify(key, _key=key)
    if t0 is not None and t0.detail == "tier0:exact":
        t0_tree, t0_exact = None, True
    else:
        t0_tree, t0_exact = t0, False
    return ScanFolderContext(
        folder_key=key,
        folder_parts=parts,
        t0_tree=t0_tree,
        t0_exact=t0_exact,
        t1=modules["env_paths"].classify(key, _key=key),
        t5=modules["registry"].classify(key, _key=key),
        t2_scan=not modules["categories"].has_folder_marker(parts),
        t4_scan=not modules["apps"].has_folder_marker(parts),
        name_cache={},
    )


def classify_scan_path(
    ctx: ScanFolderContext,
    *,
    file_key: str,
    file_name: str,
) -> KBResult:
    """Exact per-file classification beneath a prepared folder context.

    Dispatch order matches ``kb.classify`` (0 -> 5, first match wins): tiers 0
    and 1 inherit directly (a file descends within its folder's match span);
    tiers 2 and 3 run per file always (the file's own name/extension can
    change the verdict); tier 4 runs per file; tier 5 is re-tested only as the
    last-resort fallback for a file beneath an already-matched install root.

    ``file_key`` is the file's pre-normalized path; ``file_name`` its basename
    (pre-lowercased handling identical to ``components``).
    """
    modules = _tier_modules()
    if ctx.t0_tree is not None:
        r = ctx.t0_tree
        return KBResult(path=file_key, category=r.category, tier=0,
                        confidence_hint=r.confidence_hint, detail=r.detail)
    if ctx.t1 is not None:
        r = ctx.t1
        return KBResult(path=file_key, category=r.category, tier=1,
                        confidence_hint=r.confidence_hint, detail=r.detail)
    name = file_name.lower()
    cache = ctx.name_cache
    if cache is not None:
        hit = cache.get(name, _MISS)
        if hit is not _MISS:
            if hit is None:
                if ctx.t5 is not None:
                    result = modules["registry"].classify(file_key, _key=file_key)
                    if result is not None:
                        return result
                return KBResult(path=file_key, category="unknown",
                                confidence_hint="low")
            return KBResult(path=file_key, category=hit.category, tier=hit.tier,
                            confidence_hint=hit.confidence_hint, level=hit.level,
                            detail=hit.detail)
    if ctx.t2_scan:
        result = modules["categories"].classify_scan_name(file_key, name)
    else:
        result = modules["categories"].classify(
            file_key, _key=file_key, _parts=ctx.folder_parts + (name,))
    if result is not None:
        _remember(ctx, name, result)
        return result
    if ctx.t4_scan:
        result = modules["apps"].classify_scan_name(file_key, name)
    else:
        result = modules["apps"].classify(
            file_key, _key=file_key, _parts=ctx.folder_parts + (name,))
    if result is not None:
        _remember(ctx, name, result)
        return result
    if ctx.t5 is not None:
        result = modules["registry"].classify(file_key, _key=file_key)
        if result is not None:
            return result
    _remember(ctx, name, None)
    return KBResult(path=file_key, category="unknown", confidence_hint="low")


def _remember(ctx: ScanFolderContext, name: str, result) -> None:
    """Store a tier-2/3/4 filename verdict in the bounded per-folder cache.

    None means "both component tiers missed" so a repeated name skips straight
    to the tier-5 fallback / unknown exactly as the missed path would.
    """
    cache = ctx.name_cache
    if cache is not None and len(cache) < _NAME_CACHE_CAP:
        cache[name] = result


def classify_content(path: str, level: int = 2) -> KBResult:
    """Bounded-content classification (Level 2 magic bytes / Level 3 targeted)."""
    from .content import classify_content as _content

    return _content(path, level=level)


def reset_session_caches() -> None:
    """Clear per-scan-session caches (env/Known Folders + registry)."""
    from . import env_paths, registry

    env_paths.reset_cache()
    registry.reset_cache()