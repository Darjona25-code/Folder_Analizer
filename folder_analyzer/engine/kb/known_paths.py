"""Tier 0 — critical Windows/system paths.

A path is Tier 0 when any of its normalized ancestors *exactly equals* one of
the critical roots; lookups are binary searches (``bisect``) over module-level
sorted lists, never rebuilt per call. Two containment scopes keep the rule
protective without overflagging:

- ``EXACT`` roots (the system drive root): only the root *itself* matches —
  a blanket "everything under ``C:\\``" rule would classify every user file
  as system.
- ``TREE`` roots (Windows dir, System32/SysWOW64, Program Files, ProgramData,
  ``$Recycle.Bin``, ``System Volume Information``, ``Recovery``): the root and
  every descendant is ``system``.

Both lists are resolved once from the environment at module import and kept
sorted. Tier 0 feeds the protected-path policy (roadmap §10) and is the same
family as the Phase 1 security guard's critical/system protection.
"""

from __future__ import annotations

import bisect
import os
from typing import List, Optional

from ._norm import norm
from .result import KBResult

_CATEGORY = "system"


def _resolve_roots() -> "tuple[List[str], List[str]]":
    """(exact roots, tree roots) built once from the live environment."""
    env = os.environ
    drive = (env.get("SystemDrive") or "C:") + os.sep
    drive_norm = norm(drive)

    exact = {drive_norm}
    tree = set()

    for key in (
        "SystemRoot",
        "windir",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramData",
        "ALLUSERSPROFILE",
    ):
        value = env.get(key)
        if value:
            tree.add(norm(value))

    system_root = env.get("SystemRoot")
    if system_root:
        tree.add(norm(system_root))
        tree.add(norm(os.path.join(system_root, "System32")))
        tree.add(norm(os.path.join(system_root, "SysWOW64")))

    # Stable critical locations regardless of environment content.
    for extra in ("System Volume Information", "Recovery", "$Recycle.Bin"):
        tree.add(norm(os.path.join(drive, extra)))

    # Prune subsumed tree roots: if a root is under another tree root, the
    # ancestor walk already hits the broader root first, so drop the nested
    # one to keep the sorted list minimal.
    tree_list = sorted(tree)
    pruned = []
    for root in tree_list:
        if any(root != other and root.startswith(other + os.sep)
               for other in pruned):
            continue
        pruned.append(root)

    return sorted(exact), pruned


_EXACT, _TREE = _resolve_roots()


def classify(path: str, *, _key: Optional[str] = None) -> Optional[KBResult]:
    """Tier 0 verdict: ``system`` when the path is a critical root or under one.

    ``EXACT`` roots match the path *itself* only (a drive root is critical,
    but its descendants are not — otherwise every user file would be system);
    ``TREE`` roots match the path and every descendant.

    The tree test is a prefix comparison against the small root list instead of
    materializing the path's full ancestor list (same descendant-or-equal
    semantics; bound-allocations dropped for the 50k-file scan path).
    """
    key = _key if _key is not None else norm(path)
    idx = bisect.bisect_left(_EXACT, key)
    if idx < len(_EXACT) and _EXACT[idx] == key:
        return KBResult(path=key, category=_CATEGORY, tier=0,
                        confidence_hint="high", detail="tier0:exact")
    for root in _TREE:
        if key == root or key.startswith(root + os.sep):
            return KBResult(path=key, category=_CATEGORY, tier=0,
                            confidence_hint="high", detail="tier0:tree")
    return None