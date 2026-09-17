"""Shared helpers for the Phase 12 E2E harness (TASK 2).

The throwaway scan tree ``C:\\fa_e2e_phase12`` is deliberately located OUTSIDE
%TEMP% and contains no Tier-1/Tier-2 path markers, so real-environment
classification matches the committed conventions (conftest rationale). Every
surface rebuilds the identical tree before its own run, so CLI / Web / Desktop
all scan byte-identical content.
"""

from __future__ import annotations

import json
import os
import shutil

from folder_analyzer.scanner import Scanner, sort_folders_by_size

TREE = r"C:\fa_e2e_phase12"


def _write(rel: str, payload: bytes) -> None:
    path = os.path.join(TREE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(payload)


def build_tree(root: str = TREE) -> None:
    if os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)

    _write("README.md", b"# Phase 12 E2E tree\n")
    _write(os.path.join("Data", "notes.txt"), b"user content\n")
    _write(os.path.join("Data", "cache", "a.tmp"), b"tmp\n")
    _write(os.path.join("Data", "cache", "b.tmp"), b"tmp\n")
    _write(os.path.join("Data", "archives.zip"), b"\x50\x4b\x05\x06" + b"\x00" * 18)
    _write(os.path.join("Downloads", "manual.pdf"), b"%PDF-1.4\n")
    _write(os.path.join("Downloads", "setup_installer.exe"), b"MZ" + b"\x00" * 100)
    _write(os.path.join("projects", "wiki_x", "payload.data"), b"???\n")
    _write(os.path.join("projects", "src", "main.py"), b"print(1)\n")


def wipe(root: str = TREE) -> None:
    if os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)


def scan_tree(root: str = TREE):
    scanner = Scanner(max_workers=16)
    tree = scanner.scan(root)
    return tree, scanner.scan_result(), scanner


def ranked_paths(tree) -> list[str]:
    """Mirror the CLI/controller 'top folders' ranking (root excluded)."""
    return [os.path.normpath(f.path) for f in sort_folders_by_size(tree, top_n=50)]


def index_of(ranked: list[str], path: str) -> int:
    norm = os.path.normpath(path)
    for i, p in enumerate(ranked):
        if p == norm:
            return i
    raise AssertionError(f"{norm} not present in ranked folders: {ranked}")


def scan_snapshot(scan_result) -> dict:
    """Per-folder assessment keys, excluding any localized text."""
    out = {}
    for path, agg in scan_result.per_folder.items():
        a = agg.assessment
        out[path] = (
            {
                "recommendation": a.recommendation.value,
                "confidence": a.confidence.value,
                "impact": a.impact.value,
                "reason_key": a.reason_key,
                "reason_params": a.reason_params,
                "detected_category": a.detected_category,
                "is_user_data": bool(a.is_user_data),
                "is_temporary": bool(a.is_temporary),
            }
            if a is not None
            else None
        )
    return out


def export_snapshot(json_path: str) -> dict:
    """Load a v2 JSON export and drop the volatile scan_date field."""
    payload = json.load(open(json_path, "r", encoding="utf-8"))
    payload.pop("scan_date", None)
    return payload