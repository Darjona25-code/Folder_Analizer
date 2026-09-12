"""Tier 5 — optional registry app catalog (batch-loaded once per scan session).

Windows Uninstall keys (HKLM/HKCU, 64- and 32-bit views) are read **once per
scan session** into a session cache mapping normalized ``InstallLocation`` ->
app name — never per-path. This is the roadmap §10 convention confirmed here
explicitly: registry access batch-loads once, and Known Folder resolution in
``env_paths`` applies the identical once-per-session caching principle.

Degradation contract (roadmap §10 / Phase-1 convention): registry absence or
any read failure yields an EMPTY catalog — Tier 5 is optional and never a hard
dependency (``classify`` returns ``None``; the dispatcher falls through to
``unknown``).

Real-world dispatch note: most installed applications live under Program Files
/ AppData — known Tier-1 locations — so first-match-wins labels them with the
Tier-1 location category. Tier 5 fires for custom install roots *outside*
known locations (e.g. ``D:\\Apps\\…``), which is exactly the auxiliary-root
case space-reclamation scans target.

``reset_cache()`` clears the per-scan-session catalog (scan boundaries/tests).
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional

from ._norm import norm
from .result import KBResult

if sys.platform == "win32":
    import winreg
else:  # pragma: no cover - exercised on non-Windows CI where available
    winreg = None  # type: ignore[assignment]

_CATEGORY = "app"

if winreg is not None:
    _UNINSTALL_ROOTS = (
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
else:
    _UNINSTALL_ROOTS = ()

_CATALOG: Optional[Dict[str, str]] = None  # norm(InstallLocation) -> app name


def _batch_load() -> Dict[str, str]:
    """Read every Uninstall key once; on any failure return the empty catalog."""
    if winreg is None:
        return {}
    catalog: Dict[str, str] = {}
    try:
        for hive, subkey in _UNINSTALL_ROOTS:
            try:
                key = winreg.OpenKey(hive, subkey)
            except OSError:
                continue
            try:
                index = 0
                while True:
                    try:
                        name = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        app_key = winreg.OpenKey(key, name)
                    except OSError:
                        continue
                    try:
                        try:
                            display = winreg.QueryValueEx(app_key, "DisplayName")[0]
                        except OSError:
                            display = None
                        try:
                            location = winreg.QueryValueEx(
                                app_key, "InstallLocation")[0]
                        except OSError:
                            location = None
                        if display and location:
                            catalog[norm(location)] = display
                    finally:
                        app_key.Close()
            finally:
                key.Close()
    except Exception:
        return {}
    return catalog


def _catalog() -> Dict[str, str]:
    global _CATALOG
    if _CATALOG is None:
        try:
            _CATALOG = _batch_load()
        except Exception:
            _CATALOG = {}  # safe-empty: registry refresh must never raise
    return _CATALOG


def classify(path: str) -> Optional[KBResult]:
    if winreg is None:
        return None
    key = norm(path)
    for root, app in _catalog().items():
        if key == root or key.startswith(root + os.sep):
            return KBResult(path=key, category=_CATEGORY, tier=5,
                            confidence_hint="high",
                            detail=f"tier5:registry:{app}")
    return None


def reset_cache() -> None:
    """Clear the per-scan-session registry catalog (scan boundaries/tests)."""
    global _CATALOG
    _CATALOG = None