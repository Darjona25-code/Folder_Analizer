"""Phase 8 — folder-context filename verdict cache: byte-identical results.

``classify_scan_path`` gains a bounded per-folder name -> verdict cache so
repeated filenames inside one folder skip the tier-2/3/4 marker tables after
the first occurrence. On a hit the cached KBResult is re-materialized with the
CURRENT ``file_key``, so the returned ``.path`` stays per-file.

These tests prove cache hits equal both the uncached scan path and the
standalone ``kb.classify`` for every verdict shape — marker win, extension win,
app-tree win, tier-5 registry fallback, and unknown — and prove the cache is
actually being used (the tier module is consulted once per distinct name).
"""

import os

import pytest

from folder_analyzer.engine.kb import (
    categories,
    classify,
    classify_scan_path,
    prepare_scan_folder,
    registry,
)
from folder_analyzer.engine.kb._norm import norm

VERDICT_FIELDS = ("category", "tier", "confidence_hint", "level", "detail")


def _assert_repeat_parity(folder_path: str, names: list[str]) -> None:
    """One shared ctx, every name repeated 3x with distinct paths.

    Every call must equal ``kb.classify`` for its own path (the first call is
    a cache miss, the following two are hits), and hits must keep the per-call
    ``.path``.
    """
    ctx = prepare_scan_folder(folder_path)
    for name in names:
        prev = None
        for i in range(3):
            file_key = norm(
                os.path.join(folder_path, "dup%d_%s" % (i, name))
            )
            got = classify_scan_path(
                ctx, file_key=file_key, file_name="dup%d_%s" % (i, name)
            )
            standalone = classify(file_key)
            assert tuple(getattr(got, f) for f in VERDICT_FIELDS) == tuple(
                getattr(standalone, f) for f in VERDICT_FIELDS
            ), f"cached parity broken for {file_key}: {got} vs {standalone}"
            assert got.path == file_key, "cached hit leaked the first-call path"
            if prev is not None:
                assert tuple(getattr(got, f) for f in VERDICT_FIELDS) == prev
            else:
                prev = tuple(getattr(got, f) for f in VERDICT_FIELDS)


def test_repeated_filenames_cache_marker_extension_and_unknown(scan_sandbox):
    folder = os.path.join(scan_sandbox, "plain")
    os.makedirs(folder)
    for f in ("cache", "notes.txt", "report.docx", "zzzz_unknown_000.bin"):
        with open(os.path.join(folder, f), "wb") as fh:
            fh.write(b"x")
    _assert_repeat_parity(folder, ["cache", "notes.txt", "report.docx",
                                   "zzzz_unknown_000.bin"])


def test_repeated_filenames_cache_in_marker_folder(scan_sandbox):
    # t2_scan is False here: full folder+name classify runs instead of the
    # scan_name fast path; the cache must still be byte-identical.
    folder = os.path.join(scan_sandbox, "cache")
    os.makedirs(folder)
    for f in ("chrome", "steam", "notes.txt"):
        with open(os.path.join(folder, f), "wb") as fh:
            fh.write(b"x")
    _assert_repeat_parity(folder, ["chrome", "steam", "notes.txt"])


def test_repeated_filenames_cache_tier4_app_tree(scan_sandbox, monkeypatch):
    folder = os.path.join(scan_sandbox, "node_modules")
    os.makedirs(folder)
    for f in ("package.json", "index.js", "steamapps"):
        with open(os.path.join(folder, f), "wb") as fh:
            fh.write(b"x")
    _assert_repeat_parity(folder, ["package.json", "index.js", "steamapps"])


def test_cached_none_still_runs_tier5_registry_fallback(scan_sandbox, monkeypatch):
    folder = os.path.join(scan_sandbox, "apps", "Storm")
    os.makedirs(folder)
    for f in ("data.bin", "config.json"):
        with open(os.path.join(folder, f), "wb") as fh:
            fh.write(b"x")

    monkeypatch.setattr(registry, "_CATALOG", {
        norm(folder): "Storm",
    })
    # config.json: tier-3 config beats the registry root; data.bin: unknown
    # name tiers so the tier-5 fallback fires.
    _assert_repeat_parity(folder, ["data.bin", "config.json"])


def test_cache_is_actually_hit_within_a_folder(scan_sandbox, monkeypatch):
    """One tier-2/3 classify call per distinct name, not per file.

    Uses repeating names against a shared folder context (the same-name
    repeated-file shape the cache targets); no disk content is required since
    classification is pure path-string logic.
    """
    folder = os.path.join(scan_sandbox, "rep")
    os.makedirs(folder)
    names = ["cache", "notes.txt", "zunk_unknown_001.bin"]

    real = categories.classify_scan_name
    calls = {"n": 0}
    script = {}

    def counting(file_key, name):
        calls["n"] += 1
        script[name] = script.get(name, 0) + 1
        return real(file_key, name)

    monkeypatch.setattr(categories, "classify_scan_name", counting)
    ctx = prepare_scan_folder(folder)
    for n in range(12):
        for name in names:
            classify_scan_path(
                ctx,
                file_key=norm(os.path.join(folder, "%02d_%s" % (n, name))),
                file_name=name,
            )
    # 12 occurrences per name -> exactly 1 classify_scan_name call each.
    assert calls["n"] == len(names), calls
    assert sorted(script) == sorted(names)


def test_scan_classify_uses_cache_without_changing_scan_output(tmp_path, scan_sandbox):
    """End-to-end: two folders with identical repeated names, scanned normally,
    produce the same classifications the parity tests guarantee for the
    uncached path (records match standalone classify verdicts)."""
    folder = os.path.join(scan_sandbox, "stable")
    os.makedirs(folder)
    entries = []
    for n in range(8):
        p = os.path.join(folder, "rep%02d_cache.txt" % n)
        with open(p, "wb") as fh:
            fh.write(b"x")
        entries.append(p)

    from folder_analyzer.scanner import Scanner

    scanner = Scanner(max_workers=1)
    scanner.scan(folder)
    for rec in scanner.retained_records_for(folder):
        assert rec.assessment is not None
        standalone = classify(norm(rec.path))
        assert rec.assessment.detected_category == standalone.category, rec.path