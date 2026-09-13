"""Shared test fixtures (Phase 5).

``scan_sandbox`` makes scan-path classification deterministic. pytest tmp dirs
live under %TEMP%, whose literal ``temp`` path component matches Tier 2 and
reclassifies EVERY file as disposable cache. The fixture (a) neutralizes
Tier-1 environment locations / Known Folders and (b) creates a throwaway scan
root directly under the real user profile (captured at conftest import, before
any env patching) whose components contain no Tier-1/Tier-2 markers, so real
scan trees classify purely by extensions / path markers.
"""

import os

import pytest

import folder_analyzer.engine.kb.env_paths as env_paths
from folder_analyzer.engine.kb import reset_session_caches

# Captured at import time (pytest startup) — before any test patches os.environ.
_REAL_USERPROFILE = os.environ.get("USERPROFILE") or os.path.expanduser("~")


@pytest.fixture
def classification_neutral_env(monkeypatch):
    monkeypatch.setenv("TEMP", "C:\\fa_neutral\\temp")
    monkeypatch.setenv("TMP", "C:\\fa_neutral\\temp")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\fa_neutral\\localappdata")
    monkeypatch.setenv("APPDATA", "C:\\fa_neutral\\roaming")
    monkeypatch.setenv("USERPROFILE", "C:\\fa_neutral\\profile")
    monkeypatch.setenv("PROGRAMDATA", "C:\\fa_neutral\\programdata")
    monkeypatch.setenv("PROGRAMFILES", "C:\\fa_neutral\\programfiles")
    monkeypatch.setenv("PROGRAMFILES(X86)", "C:\\fa_neutral\\programfiles_x86")

    orig_lookup = env_paths._known_folder_path
    env_paths._known_folder_path = lambda _key: None
    reset_session_caches()
    yield
    env_paths._known_folder_path = orig_lookup
    reset_session_caches()


@pytest.fixture
def scan_sandbox(classification_neutral_env):
    """Marker-free, env-neutral scan root for classification-sensitive tests."""
    import shutil
    import tempfile

    root = tempfile.mkdtemp(prefix=".fa_phase5_", dir=_REAL_USERPROFILE)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
        reset_session_caches()