"""Folder-context scan classification: exact parity with standalone kb.classify.

The scanner's hot path classifies each file with a pre-resolved
``kb.prepare_scan_folder`` context (``classify_scan_path``) so the
folder-transitive tiers (0/1/5) are resolved once per folder. These tests prove
that path is BYTE-IDENTICAL to the standalone ``kb.classify`` dispatch for
every file — including the shapes that would break a naive "folder verdict
inherits" shortcut:

- filename-only Tier-2 markers (``dev\\cache``: the file name adds cache while
  the folder alone would not match it),
- marker reordering (``cache\\steam``: the game group precedes the cache group
  when the folder *and* the file contribute different markers),
- a Tier-3 extension win inside a Tier-4 app tree (``node_modules\package.json``
  -> config, not app:node),
- dotted directory names whose own "extension" is NOT a filename fact
  (``cache.tmp\notes.txt`` resolves by the file extension, not the dir name),
- descendants of an EXACT Tier-0 root (drive root critical, files not), TREE
  roots, env roots and registry install roots.

All drive-path cases are synthetic strings (classification is path-string
logic, no disk access).
"""

from __future__ import annotations

import os

import pytest

from folder_analyzer.engine import classifier
from folder_analyzer.engine.kb import (
    apps,
    categories,
    classify,
    classify_scan_path,
    env_paths,
    known_paths,
    prepare_scan_folder,
    registry,
)
from folder_analyzer.engine.kb._norm import components, norm

VERDICT_FIELDS = ("category", "tier", "confidence_hint", "detail")


def _build_tree(root: str) -> list[str]:
    dirs = [
        "plain",
        "dev",
        "cache",
        "node_modules",
        "cache.tmp",
        "deps",
        "systree/a/b",
        "docs",
        "apps/Storm",
    ]
    for d in dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    files = [
        "plain/file.bin",            # unknown, all tiers miss
        "plain/notes.txt",           # Tier 3 documents
        "dev/cache",                 # filename-only Tier-2 cache marker in dev dir
        "cache/steam",               # folder cache + file steam -> game group wins
        "cache/chrome",              # two markers; browser group precedes cache
        "node_modules/package.json", # Tier 3 config beats Tier 4 app:node
        "node_modules/cache",        # filename-only Tier-2 cache inside app tree
        "node_modules/steamapps",    # Tier 2 game marker inside app tree
        "cache.tmp/notes.txt",       # dotted dir name must NOT be a filename fact
        "deps/x.dll",                # Tier 3 system
        "systree/a/b/data.dat",      # under a TREE root (monkeypatched test)
        "docs/report.docx",          # Tier 3 documents
        "apps/Storm/config.dat",     # registry root case (monkeypatched test)
        "apps/Storm/config.json",    # Tier 3 config beats registry
    ]
    for f in files:
        with open(os.path.join(root, f), "wb") as fh:
            fh.write(b"x")
    return [os.path.join(root, f) for f in files]


def _assert_parity(folder_path: str, file_path: str) -> None:
    ctx = prepare_scan_folder(folder_path)
    key = norm(file_path)
    name = os.path.basename(file_path)
    assert components(key) == list(ctx.folder_parts) + [name.lower()]
    scan = classify_scan_path(ctx, file_key=key, file_name=name)
    standalone = classify(file_path)
    assert (scan.category, scan.tier, scan.confidence_hint, scan.detail) == (
        standalone.category, standalone.tier,
        standalone.confidence_hint, standalone.detail,
    ), f"parity broken for {file_path}: {scan} vs {standalone}"


def test_scan_parity_mixed_tree(tmp_path: "pytest.TempPathFactory") -> None:
    root = str(tmp_path)
    for f in _build_tree(root):
        _assert_parity(os.path.dirname(f), f)


def test_scan_parity_tier0_tree_and_exact(monkeypatch) -> None:
    z = norm("Z:")
    monkeypatch.setattr(known_paths, "_EXACT", [z + os.sep])
    monkeypatch.setattr(known_paths, "_TREE", [norm("Z:" + os.sep + "systree")])
    _assert_parity("Z:\\systree\\a\\b", "Z:\\systree\\a\\b\\data.bin")

    ctx = prepare_scan_folder(norm("Z:"))
    file_path = "Z:\\notes.data"
    scan = classify_scan_path(ctx, file_key=norm(file_path), file_name="notes.data")
    standalone = classify(file_path)
    assert (scan.category, scan.tier) == (standalone.category, standalone.tier)
    assert (scan.category, scan.tier) == ("unknown", None)


def test_scan_parity_env_root(monkeypatch) -> None:
    monkeypatch.setattr(env_paths, "_RESOLVED", [
        ("documents", norm("Z:" + os.sep + "docs")),
    ])
    _assert_parity("Z:\\docs\\x", "Z:\\docs\\x\\report.docx")


def test_scan_parity_registry_root(monkeypatch) -> None:
    monkeypatch.setattr(registry, "_CATALOG", {
        norm("Z:" + os.sep + "apps" + os.sep + "Storm"): "Storm",
    })
    plain = "Z:\\apps\\Storm\\config.dat"
    nested = "Z:\\apps\\Storm\\sub\\packeddata.bin"
    jsonf = "Z:\\apps\\Storm\\config.json"
    _assert_parity(os.path.dirname(plain), plain)
    _assert_parity(os.path.dirname(nested), nested)
    _assert_parity(os.path.dirname(jsonf), jsonf)


def test_fixture_parity_classify_scan(tmp_path) -> None:
    root = str(tmp_path)
    for f in _build_tree(root):
        ctx = prepare_scan_folder(os.path.dirname(f))
        assert ctx.folder_key + os.sep + os.path.basename(f).lower() == norm(f)
        a = classifier.classify_scan(f, filename=os.path.basename(f), _ctx=ctx)
        b = classifier.classify_scan(f, filename=os.path.basename(f))
        assert a == b
        assert a.bucket == b.bucket


def test_tier_modules_accept_parts_without_behavior_change(tmp_path) -> None:
    root = str(tmp_path)
    for f in _build_tree(root)[:6]:
        key = norm(f)
        parts = components(key)
        assert categories.classify(f, _key=key, _parts=parts) == categories.classify(f)
        assert apps.classify(f, _key=key, _parts=tuple(parts)) == apps.classify(f)