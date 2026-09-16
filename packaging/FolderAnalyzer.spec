# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the desktop app (Phase 11, onedir).

Build from the repo root:

    python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/FolderAnalyzer.spec

Output: ``dist/FolderAnalyzer/FolderAnalyzer.exe`` plus Qt plugins under
``_internal``. Core ``folder_analyzer/`` is consumed in-process only
(ADR-001); nothing here rearranges core layout for the bundle.
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

a = Analysis(
    [os.path.join(ROOT, "desktop_app", "__main__.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (
            os.path.join(ROOT, "folder_analyzer", "locales", "en.json"),
            "folder_analyzer/locales",
        ),
        (
            os.path.join(ROOT, "folder_analyzer", "locales", "es.json"),
            "folder_analyzer/locales",
        ),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FolderAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FolderAnalyzer",
)