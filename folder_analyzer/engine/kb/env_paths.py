"""Tier 1 — known locations: environment variables + Windows Known Folders.

Resolution is CACHED per scan session: environment reads and
``SHGetKnownFolderPath`` calls happen at most once (on first need) and then
freeze until ``reset_cache()``. This is the same once-per-scan-session
principle the roadmap specifies for registry batch-loading (§10) — confirmed
here for Known Folder + env resolution.

Within the tier, more specific entries are evaluated before broad ones, so a
file in ``Downloads`` is ``downloads``, not ``user_profile``.

Dispatch interaction (documented): a path under a known location is labeled by
Tier 1 *first* (first-match-wins); Tiers 2-4 classify paths outside known
locations (e.g. auxiliary/external drives), which is the primary target of
space-reclamation scans.
"""

from __future__ import annotations

import ctypes
import os
from typing import List, Optional, Tuple

from ._norm import norm
from .result import KBResult

_FOLDER_GUIDS = {
    "profile": "{5E6C858F-0E22-4760-9AFE-EA3317B67173}",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "localappdata": "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
    "roamingappdata": "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
    "programdata": "{62AB5D82-45F1-4FDA-8008-26359C6D4C98}",
}

# Order is significant: most specific first. Downloads/Documents/Desktop must
# precede USERPROFILE (they are its descendants); LOCALAPPDATA/APPDATA precede
# USERPROFILE for the same reason.
_ORDERED_ENTRIES: "tuple[tuple[str, str, str], ...]" = (
    ("env", "TEMP", "temp"),
    ("env", "TMP", "temp"),
    ("folder", "downloads", "downloads"),
    ("folder", "documents", "documents"),
    ("folder", "desktop", "desktop"),
    ("env", "LOCALAPPDATA", "app_data_local"),
    ("env", "APPDATA", "app_data_roaming"),
    ("folder", "localappdata", "app_data_local"),
    ("folder", "roamingappdata", "app_data_roaming"),
    ("folder", "programdata", "program_data"),
    ("folder", "profile", "user_profile"),
    ("env", "USERPROFILE", "user_profile"),
    ("env", "PROGRAMDATA", "program_data"),
    ("env", "PROGRAMFILES", "program_files"),
    ("env", "PROGRAMFILES(X86)", "program_files_x86"),
    ("env", "WINDIR", "system"),
)


class _GUID(ctypes.Structure):
    """Windows GUID shape (16 raw bytes) for SHGetKnownFolderPath."""

    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _parse_guid(value: str) -> _GUID:
    import uuid as _uuid

    raw = _uuid.UUID(value.strip("{}"))
    return _GUID(
        Data1=raw.time_low,
        Data2=raw.time_mid,
        Data3=raw.time_hi_version,
        Data4=(ctypes.c_ubyte * 8)(*raw.bytes[8:]),
    )


def _known_folder_path(folder_key: str) -> Optional[str]:
    """Resolve a Windows Known Folder via SHGetKnownFolderPath (win32 only).

    Returns None on any failure — Known Folders are best-effort, never a hard
    dependency (same degradation contract as Tier 5 registry).
    """
    if os.name != "nt":
        return None
    try:
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        buffer = ctypes.c_wchar_p()
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(_parse_guid(_FOLDER_GUIDS[folder_key])),
            0,
            None,
            ctypes.byref(buffer),
        )
        if result != 0:
            return None
        value = buffer.value
        ctypes.windll.ole32.CoTaskMemFree(buffer)
        return value
    except Exception:
        return None


_RESOLVED: Optional[List[Tuple[str, str]]] = None  # (category, normalized root)


def _resolve_all() -> List[Tuple[str, str]]:
    """Build the session cache in most-specific-first order."""
    resolved = []
    for kind, name, category in _ORDERED_ENTRIES:
        value = (
            os.environ.get(name)
            if kind == "env"
            else _known_folder_path(name)
        )
        if value:
            resolved.append((category, norm(value)))
    return resolved


def _resolved() -> List[Tuple[str, str]]:
    global _RESOLVED
    if _RESOLVED is None:
        _RESOLVED = _resolve_all()
    return _RESOLVED


def classify(path: str, *, _key: Optional[str] = None) -> Optional[KBResult]:
    key = _key if _key is not None else norm(path)
    for category, root in _resolved():
        if key == root or key.startswith(root + os.sep):
            return KBResult(path=key, category=category, tier=1,
                            confidence_hint="high", detail="tier1:location")
    return None


def reset_cache() -> None:
    """Clear the per-scan-session resolution cache (scan boundaries/tests)."""
    global _RESOLVED
    _RESOLVED = None