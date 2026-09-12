"""Phase 4 — Knowledge Base: tiered classification, caching, bounded reads.

Covers (roadmap §10 + Phase 4 scope):
- Tier-by-tier classification correctness (T0 exact/tree, T1 env + Known
  Folders, T2 component patterns, T3 extensions, T4 app rules, T5 registry).
- Dispatch order: first match wins (0 -> 5), nothing matched -> "unknown".
- Tier 0 binary-search exact-match semantics (drive root itself, not its
  descendants; tree roots cover descendants).
- Tier 1 + Tier 5 session caching: resolved once per scan session, repeated
  classify() calls never re-read (counted, mirroring the Phase 3 syscall
  counting pattern).
- Level 2/3 bounded-read proof on a >100 MB sparse file (never a full read).
- Unknown stays unknown: unrecognizable input never yields a positive category
  and the KB never constructs an Assessment / recommendation.
"""

import builtins
import os

import pytest

import folder_analyzer.engine.kb as kb
from folder_analyzer.engine.kb import (
    categories,
    content,
    env_paths,
    known_paths,
    registry,
)
from folder_analyzer.engine.kb.result import KBResult


@pytest.fixture(autouse=True)
def _reset_kb_session():
    kb.reset_session_caches()
    yield
    kb.reset_session_caches()


# ---------------------------------------------------------------------------
# 1. Tier 0 — critical/system paths (exact set + binary search)
# ---------------------------------------------------------------------------

def test_tier0_lists_are_sorted_for_binary_search():
    assert known_paths._EXACT == sorted(known_paths._EXACT)
    assert known_paths._TREE == sorted(known_paths._TREE)
    assert known_paths._EXACT  # never empty on a real machine


def test_tier0_drive_root_matches_itself_only():
    drive_root = os.environ.get("SystemDrive", "C:") + os.sep
    result = known_paths.classify(drive_root)
    assert result is not None
    assert result.tier == 0 and result.category == "system"
    # The drive root's descendants are NOT system (otherwise every user file
    # would be Tier 0): the exact set must never leak down the ancestor walk.
    not_system = os.path.join(os.environ.get("USERPROFILE", drive_root), "x.txt")
    assert known_paths.classify(not_system) is None


def test_tier0_tree_root_covers_descendants():
    system_root = os.environ["SystemRoot"]
    deep = os.path.join(system_root, "System32", "drivers", "etc", "hosts")
    result = known_paths.classify(deep)
    assert result is not None
    assert result.tier == 0 and result.category == "system"
    assert result.detail == "tier0:tree"


def test_tier0_noncritical_path_is_none():
    assert known_paths.classify("P:\\scratch\\notes.txt") is None


# ---------------------------------------------------------------------------
# 2. Tier 1 — env vars + Known Folders, cached once per session
# ---------------------------------------------------------------------------

def test_tier1_env_locations():
    profile = os.path.join(os.environ["USERPROFILE"], "notes.txt")
    result = env_paths.classify(profile)
    assert result is not None
    assert result.tier == 1 and result.category == "user_profile"

    temp = os.path.join(os.environ["TEMP"], "x.tmp")
    result = env_paths.classify(temp)
    assert result is not None
    assert result.tier == 1 and result.category == "temp"


def test_tier1_downloads_known_folder_beats_user_profile():
    """Downloads is checked before USERPROFILE (more specific first)."""
    profile_downloads = os.path.join(os.environ["USERPROFILE"], "Downloads")
    result = env_paths.classify(os.path.join(profile_downloads, "a.zip"))
    if result is not None:
        # If the real Downloads folder resolves under the profile, the Known
        # Folder entry must win over the generic user_profile label.
        if env_paths._known_folder_path("downloads") is not None:
            assert result.category == "downloads"


def test_env_and_known_folder_resolution_is_cached_once_per_session():
    """Resolution is a batch of N Known-Folder lookups; must run once per
    session until reset_cache()."""
    calls = {"count": 0}

    def fake_known_folder(key):
        calls["count"] += 1
        return "P:\\knownroot"

    expected = sum(1 for kind, _, _ in env_paths._ORDERED_ENTRIES if kind == "folder")

    orig = env_paths._known_folder_path
    env_paths._known_folder_path = fake_known_folder
    try:
        kb.reset_session_caches()
        assert env_paths.classify("P:\\knownroot\\a.zip").category == "downloads"
        assert env_paths.classify("P:\\knownroot\\b.zip").category == "downloads"
        assert env_paths.classify("P:\\knownroot\\c\\d.jpg").category == "downloads"
        assert calls["count"] == expected, \
            "Known Folder resolution must batch once per session"

        kb.reset_session_caches()
        assert env_paths.classify("P:\\knownroot\\e.txt").category == "downloads"
        assert calls["count"] == 2 * expected, \
            "reset_cache() must restart the session cache"
    finally:
        env_paths._known_folder_path = orig


def test_known_folder_real_resolution_win32():
    raw = env_paths._known_folder_path("downloads")
    if raw is None:
        pytest.skip("SHGetKnownFolderPath unavailable")
    assert os.path.isabs(raw)
    assert os.path.dirname(raw)  # not a bare drive root


# ---------------------------------------------------------------------------
# 3. Tiers 2 & 3 — component patterns and extension table (first match wins)
# ---------------------------------------------------------------------------

def test_tier2_component_patterns():
    assert categories.classify("D:\\scratch\\steamapps\\common\\game.txt").category == "game"
    assert categories.classify("D:\\tmp\\scratch\\f.pdf").category == "cache"
    assert categories.classify("D:\\data\\appdata\\Local\\Chrome\\Cache\\x").category == "browser"
    assert categories.classify("D:\\proj\\.git\\objects\\pack\\x").category == "dev"
    assert categories.classify("D:\\ai\\weights\\m.gguf").category == "ai_ml"
    assert categories.classify("D:\\misc\\docker\\data\\x").category == "docker"


def test_tier2_matches_directory_names_only():
    """A file named like a marker must NOT trip the component rule."""
    result = categories.classify("D:\\misc\\steam.txt")  # file, not folder
    assert result is None or result.detail != "tier2:component"


def test_tier3_extensions():
    assert categories.classify("D:\\misc\\notes.pdf").category == "documents"
    assert categories.classify("D:\\misc\\photo.jpg").category == "media"
    assert categories.classify("D:\\misc\\bundle.zip").category == "archives"
    assert categories.classify("D:\\misc\\data.sqlite3").category == "databases"
    assert categories.classify("D:\\misc\\app.json").category == "config"
    assert categories.classify("D:\\misc\\temp.tmp").category == "temp"
    assert categories.classify("D:\\misc\\driver.sys").category == "system"


def test_tier2_beats_tier3_within_same_path():
    """Component evidence (tier 2) is decided before extension (tier 3)."""
    result = categories.classify("D:\\cache\\photo.jpg")
    assert result.tier == 2 and result.category == "cache"


# ---------------------------------------------------------------------------
# 4. Tier 4 — high-value app rules
# ---------------------------------------------------------------------------

def test_tier4_app_rules():
    # node_modules is NOT in the Tier 2/3 tables (reserved for Tier 4), so the
    # dispatcher keeps walking until the Tier 4 rule fires.
    assert categories.classify("D:\\apps\\proj\\node_modules\\pkg\\index.js") is None
    result = _fetch("D:\\apps\\proj\\node_modules\\pkg\\index.js")
    assert result.tier == 4 and result.category == "app:node"


def _fetch(path):  # dispatcher classify for a synthetic path
    return kb.classify(path)


def test_tier4_ollama_python_browser():
    # Ollama model store: only files whose extension is NOT in the Tier 3 table
    # reach Tier 4 by first-match-wins — a .json manifest is claimed by Tier 3
    # ("config"); its app:ollama attribution is a Level 3 content check (see
    # test_content_level3_ollama_manifest_confirmation).
    assert _fetch("D:\\misc\\.ollama\\models\\x.bin").category == "app:ollama"
    assert _fetch("D:\\dev\\venv\\Lib\\site-packages\\pkg\\x.py").category == "app:python"
    assert _fetch("D:\\misc\\user data\\Default\\Cookies").category == "app:browser"
    # A .mozilla/firefox profile dir carries Tier 2 brand evidence first,
    # so first-match-wins labels it "browser" (not the Tier 4 app: rule).
    assert _fetch("D:\\browser\\.mozilla\\firefox\\Profiles\\x").category == "browser"


def test_dispatch_extension_shortcircuits_before_tier4():
    """First-match-wins: Tier 3 extension evidence pre-empts Tier 4 app rules."""
    result = kb.classify("D:\\ai\\ollama\\models\\manifest.json")
    assert result.tier == 3 and result.category == "config"


# ---------------------------------------------------------------------------
# 5. Tier 5 — registry, batch-loaded once per session, safe-empty
# ---------------------------------------------------------------------------

def test_registry_batch_loads_once_per_session():
    calls = {"count": 0}

    def fake_batch_load():
        calls["count"] += 1
        return {"p:\\apps\\tool": "FakeTool"}

    orig = registry._batch_load
    registry._batch_load = fake_batch_load
    try:
        registry.reset_cache()
        assert registry.classify("P:\\apps\\tool\\bin\\x.exe").category == "app"
        assert registry.classify("P:\\apps\\tool\\plugins\\y.dll").category == "app"
        assert registry.classify("P:\\apps\\unrelated\\z.txt") is None
        assert calls["count"] == 1, "registry must batch-load exactly once"

        registry.reset_cache()
        assert registry.classify("P:\\apps\\tool\\bin\\x.exe").category == "app"
        assert calls["count"] == 2
    finally:
        registry._batch_load = orig


def test_registry_safe_empty_on_failure():
    def exploding_load():
        raise OSError("registry unavailable")

    orig = registry._batch_load
    registry._batch_load = exploding_load
    try:
        registry.reset_cache()
        assert registry.classify("P:\\apps\\anything\\x.zzk") is None
        # And the dispatcher degrades to unknown without raising.
        result = kb.classify("P:\\apps\\anything\\x.zzk")
        assert result.category == "unknown"
        assert not hasattr(result, "recommendation")
    finally:
        registry._batch_load = orig


# ---------------------------------------------------------------------------
# 6. Dispatch: first match wins (0 -> 5), unknown stays unknown
# ---------------------------------------------------------------------------

def test_dispatch_tier0_wins_over_tier3():
    path = os.path.join(os.environ["SystemRoot"], "notes.pdf")
    result = kb.classify(path)
    assert result.tier == 0 and result.category == "system"


def test_dispatch_tier1_wins_over_tier3():
    path = os.path.join(os.environ["USERPROFILE"], "notes.pdf")
    result = kb.classify(path)
    assert result.tier == 1 and result.category == "user_profile"


def test_dispatch_tier2_wins_over_tier3():
    result = kb.classify("D:\\cache\\photo.jpg")
    assert result.tier == 2 and result.category == "cache"


def test_dispatch_unknown_stays_unknown_no_forced_category():
    result = kb.classify("P:\\scratch\\xyq-2026.zzk")
    assert result.category == "unknown"
    assert result.tier is None
    assert result.confidence_hint == "low"
    # The KB must never hand back a recommendation/assessment-like field.
    assert not hasattr(result, "recommendation")
    assert not hasattr(result, "assessment")


def test_dispatch_each_tier_module_returns_kbresult_or_none():
    from folder_analyzer.engine.kb import apps

    for path in ("P:\\a\\b.txt", "D:\\cache\\x.log", "C:\\"):
        for fn in (known_paths.classify, env_paths.classify,
                   categories.classify, apps.classify, registry.classify):
            out = fn(path)
            assert out is None or isinstance(out, KBResult)


# ---------------------------------------------------------------------------
# 7. Level 2/3 bounded reads — a >100 MB file is never fully read
# ---------------------------------------------------------------------------

class _CountingOpen:
    """Instruments builtins.open so every byte read is recorded."""

    def __init__(self):
        self.bytes_read = 0
        self._orig = builtins.open

    def __enter__(self):
        self._orig = builtins.open
        builtins.open = self._open
        return self

    def __exit__(self, *exc):
        builtins.open = self._orig
        return False

    def _open(self, file, *args, **kwargs):
        raw = self._orig(file, *args, **kwargs)
        if not hasattr(raw, "read"):
            return raw
        return _CountingHandle(self, raw)


class _CountingHandle:
    def __init__(self, counter, raw):
        self._counter = counter
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._raw.close()
        return False

    def read(self, size=-1):
        data = self._raw.read(size)
        self._counter.bytes_read += len(data)
        return data

    def close(self):
        self._raw.close()


@pytest.fixture
def huge_ambiguous_file(tmp_path):
    target = tmp_path / "huge.bin"
    with open(target, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
    with open(target, "rb+") as fh:
        fh.truncate(120 * 1024 * 1024)  # sparse: 120 MB logical size
    assert os.path.getsize(target) > 100 * 1024 * 1024
    return target


def test_level2_large_file_bounded_read(huge_ambiguous_file):
    counter = _CountingOpen()
    with counter:
        result = kb.classify_content(str(huge_ambiguous_file), level=2)
    assert result.category == "media"  # PNG magic resolves the ambiguity
    assert result.level == 2
    assert 0 < counter.bytes_read <= content.LEVEL2_MAX_BYTES
    assert counter.bytes_read < os.path.getsize(huge_ambiguous_file)


def test_level3_large_file_bounded_read(huge_ambiguous_file):
    counter = _CountingOpen()
    with counter:
        result = kb.classify_content(str(huge_ambiguous_file), level=3)
    assert result.category == "media"
    assert result.level == 3
    assert 0 < counter.bytes_read <= content.LEVEL3_MAX_BYTES
    assert counter.bytes_read < os.path.getsize(huge_ambiguous_file)


# ---------------------------------------------------------------------------
# 8. Content analysis: Level 3 targeted cases + unknown stays unknown
# ---------------------------------------------------------------------------

def test_content_level3_ollama_manifest_confirmation(tmp_path):
    manifest_dir = tmp_path / "ollama" / "manifests"
    manifest_dir.mkdir(parents=True)
    manifest = manifest_dir / "registry-1.docker.io.json"
    manifest.write_text('{"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json", "layers": []}')
    assert kb.classify_content(str(manifest), level=3).category == "app:ollama"
    # Level 2 has no magic for JSON -> unknown, Level 3 refines for the exact
    # documented ollama+manifests shape ONLY.
    assert kb.classify_content(str(manifest), level=2).category == "unknown"


def test_content_level3_ollama_does_not_generalize(tmp_path):
    """Same JSON shape elsewhere must NOT be called Ollama."""
    other = tmp_path / "anywhere" / "manifest.json"
    other.parent.mkdir(parents=True)
    other.write_text('{"schemaVersion": 2, "mediaType": "x", "layers": []}')
    assert kb.classify_content(str(other), level=3).category == "unknown"


def test_content_unknown_stays_unknown(tmp_path):
    blob = tmp_path / "random.dat"
    blob.write_bytes(b"\x99\x88\x77\x66\x55\x44" * 64)
    result = kb.classify_content(str(blob), level=2)
    assert result.category == "unknown"
    assert result.tier is None
    assert not hasattr(result, "recommendation")
    result = kb.classify_content(str(blob), level=3)
    assert result.category == "unknown"


def test_content_missing_file_degrades_to_unknown(tmp_path):
    missing = tmp_path / "nope.bin"
    result = kb.classify_content(str(missing), level=2)
    assert result.category == "unknown"
    assert result.confidence_hint == "low"


def test_content_level_must_be_2_or_3():
    with pytest.raises(ValueError):
        kb.classify_content("P:\\x.bin", level=1)
    with pytest.raises(ValueError):
        kb.classify_content("P:\\x.bin", level=4)


# ---------------------------------------------------------------------------
# 9. KBResult value contract
# ---------------------------------------------------------------------------

def test_kbresult_validation():
    with pytest.raises(ValueError):
        KBResult(path="a", confidence_hint="certain")
    with pytest.raises(ValueError):
        KBResult(path="a", tier=9)
    with pytest.raises(ValueError):
        KBResult(path="a", level=4)


def test_reset_session_caches_invalidates_env_and_registry():
    calls = {"env": 0, "registry": 0}

    def fake_folder(key):
        calls["env"] += 1
        return "P:\\knownroot"

    def fake_batch_load():
        calls["registry"] += 1
        return {}

    orig_f, orig_r = env_paths._known_folder_path, registry._batch_load
    env_paths._known_folder_path, registry._batch_load = fake_folder, fake_batch_load
    try:
        expected_env = sum(1 for kind, _, _ in env_paths._ORDERED_ENTRIES
                           if kind == "folder")
        kb.reset_session_caches()
        kb.classify("P:\\knownroot\\x.txt")
        kb.classify("P:\\apps\\y\\z")
        kb.classify("P:\\knownroot\\w.txt")
        assert calls["env"] == expected_env and calls["registry"] == 1

        kb.reset_session_caches()
        kb.classify("P:\\knownroot\\x.txt")
        kb.classify("P:\\apps\\y\\z")
        assert calls["env"] == 2 * expected_env and calls["registry"] == 2
    finally:
        env_paths._known_folder_path = orig_f
        registry._batch_load = orig_r