"""Shared path helpers for the Knowledge Base package.

Normalization, ancestor enumeration and component splitting are centralized
here so every tier resolves paths identically (case- and separator-insensitive
comparisons on Windows).
"""

from __future__ import annotations

import os
from typing import Iterator, List


def norm(path: str) -> str:
    """Normalize a path: case-normalized + lexically cleaned, OS separator."""
    return os.path.normcase(os.path.normpath(path))


def ancestors(normed: str) -> Iterator[str]:
    """Yield ``normed`` then every parent, leaf -> root.

    ``os.path.dirname`` of a drive root yields itself, so iteration stops
    there (no infinite loop).
    """
    cur = normed
    while True:
        yield cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


def components(normed: str) -> List[str]:
    """Casefolded path component names (directory names + the final name).

    Matching is against whole components only, so a file named ``fish.txt``
    never trips a "game" directory marker; only an actual ``steam``/``cache``
    … directory name does.
    """
    return [p for p in (part.lower() for part in normed.split(os.sep)) if p]