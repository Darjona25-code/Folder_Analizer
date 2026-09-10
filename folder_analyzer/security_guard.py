"""Canonical deletion security guard for Folder Analyzer (Phase 1).

Implements the six-condition deletion guard and is the single enforcement point
used by the CLI, the API, and (later) the desktop application:

    1. Valid path input.
    2. Safe canonicalization (per-component realpath + normcase over a single
       canonical reference form).
    3. Canonical containment inside the active scanned root.
    4. Root protection (the root itself; ancestors are outside the boundary and
       therefore denied by containment).
    5. Reparse-point integrity (resolution may not escape the authorized tree).
    6. Final revalidation immediately before deletion (callers re-run this
       function right before send2trash).

Design decisions honored here:

- ``\\?\\`` extended-length and canonical forms are INTERNAL representations
  only; user-facing output always uses the original human-readable path.
- There is NO blanket 260-character limit. Paths that cannot be safely
  represented/resolved/operated on are returned as ``not_resolvable``
  (denied/deferred, never guessed, never retried automatically).
- ``os.access`` is deliberately NOT part of the security boundary.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from .safety import get_risk_level, RiskLevel


class GuardStatus(str, Enum):
    OK = "ok"
    DENIED_ROOT = "denied_root"
    DENIED_CONTAINMENT = "denied_containment"
    DENIED_PROTECTED = "denied_protected"
    DENIED_CRITICAL = "denied_critical"
    NOT_RESOLVABLE = "not_resolvable"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class DeleteVerdict:
    """Result of validating a single deletion target."""

    status: GuardStatus
    original: str
    canonical: Optional[str] = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == GuardStatus.OK

    @property
    def denied(self) -> bool:
        return self.status.value.startswith("denied")

    @property
    def deferred(self) -> bool:
        return self.status == GuardStatus.NOT_RESOLVABLE


def is_valid_path_input(path: object) -> bool:
    """Condition 1: the raw input is representable and free of NUL bytes."""
    if not isinstance(path, str):
        return False
    if not path.strip():
        return False
    if "\x00" in path:
        return False
    return True


def canonical_key(path: str) -> Optional[str]:
    """Return the single canonical reference form of *path*.

    The result is the internal identity used for ALL security comparisons. A
    leading ``\\\\?\\\\`` prefix is normalized away so that an extended-length
    path and its short form compare equal. Returns ``None`` when the path cannot
    be safely resolved by the current runtime.
    """
    try:
        resolved = os.path.realpath(os.path.abspath(os.fspath(path)))
        key = os.path.normcase(os.path.normpath(resolved))
    except (OSError, ValueError, TypeError):
        return None
    if key.startswith("\\\\?\\"):
        key = key[4:]
    return key


def display_path(path: str) -> str:
    """Human-readable form for user-facing output.

    Never returns an internal ``\\\\?\\`` canonical form for a path the user
    supplied; it is simply normalized for readability.
    """
    try:
        return os.path.normpath(path)
    except (OSError, ValueError):
        return path


def path_is_within(target_key: str, root_key: str) -> bool:
    """Condition 3: component-boundary containment on canonical keys.

    Uses ``os.path.commonpath`` so ``C:\\FOO`` is NOT considered a prefix of
    ``C:\\FOOBAR`` and anchors/drive mismatches are handled by the os.path layer.
    """
    try:
        return os.path.commonpath([target_key, root_key]) == root_key
    except ValueError:
        return False


def is_protected_path(path: str, protected_roots: Iterable[str]) -> bool:
    """True if *path* equals a protected root or is an ancestor of one.

    Prevents the scanned root (or any of its parents) from being sent to the
    Recycle Bin as a side effect of deleting a sibling.
    """
    norm = os.path.normcase(os.path.normpath(path))
    for root in protected_roots:
        root_norm = os.path.normcase(os.path.normpath(root))
        if norm == root_norm:
            return True
        if root_norm.startswith(norm + os.sep):
            return True
    return False


def validate_delete_target(
    path: str,
    scan_root: Optional[str] = None,
    protected_roots: Optional[Iterable[str]] = None,
) -> DeleteVerdict:
    """Run the six-condition guard against a single candidate deletion target.

    Args:
        path: The target the user wants to delete (original, human-readable).
        scan_root: The canonical scanned root (active boundary). When None the
            containment conditions are skipped (used for legacy callers that do
            not operate on a scanned tree).
        protected_roots: Roots that must never be deleted (nor have ancestors
            deleted).

    Returns:
        A DeleteVerdict. Only ``status == OK`` authorizes deletion, and even then
        the caller must re-run this exact function immediately before send2trash.
    """
    protected_roots = list(protected_roots or [])

    # Condition 1: valid input.
    if not is_valid_path_input(path):
        return DeleteVerdict(
            GuardStatus.INVALID_INPUT, path, reason="invalid path input"
        )

    # Nonexistent target: deterministically "not found" (never guessed, never an
    # implied "safe" or "dangerous" classification).
    if not os.path.lexists(path):
        return DeleteVerdict(GuardStatus.NOT_FOUND, path, reason="path does not exist")

    # Condition 2: safe canonicalization (single canonical reference form).
    target_key = canonical_key(path)
    if target_key is None:
        return DeleteVerdict(
            GuardStatus.NOT_RESOLVABLE,
            path,
            reason="cannot safely resolve path in current runtime",
        )

    # Conditions 3 + 4: containment and root/ancestor protection. Ancestors of
    # the root are outside the boundary, so they are denied by containment.
    if scan_root is not None:
        root_key = canonical_key(scan_root)
        if root_key is None:
            return DeleteVerdict(
                GuardStatus.NOT_RESOLVABLE,
                path,
                reason="cannot safely resolve the scanned root",
            )
        if target_key == root_key:
            return DeleteVerdict(
                GuardStatus.DENIED_ROOT, path, target_key,
                reason="cannot delete the scanned root",
            )
        if not path_is_within(target_key, root_key):
            return DeleteVerdict(
                GuardStatus.DENIED_CONTAINMENT, path, target_key,
                reason="target resolves outside the scanned area (contains symlink/junction escape?)",
            )

    # Protected-path policy (includes the scan root via protected_roots).
    if is_protected_path(path, protected_roots):
        return DeleteVerdict(
            GuardStatus.DENIED_PROTECTED, path, target_key,
            reason="protected root or ancestor of a protected root",
        )

    # Critical system path policy.
    if get_risk_level(path) == RiskLevel.CRITICAL:
        return DeleteVerdict(
            GuardStatus.DENIED_CRITICAL, path, target_key,
            reason="critical system path",
        )

    return DeleteVerdict(GuardStatus.OK, path, target_key)


def revalidate(path: str, scan_root: Optional[str] = None,
               protected_roots: Optional[Iterable[str]] = None) -> DeleteVerdict:
    """Condition 6: final validation immediately before deletion.

    Callers MUST call this right before send2trash and abort if it is not OK.
    It is the same validation, re-run against the freshly resolved target.
    """
    return validate_delete_target(path, scan_root=scan_root, protected_roots=protected_roots)