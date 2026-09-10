"""Deletion security tests for the six-condition canonical deletion guard (Phase 1).

Covers the required path-representation cases from docs/ROADMAP.md §19:

- normal path inside scanned tree
- traversal segments (..) both inline and trailing
- cross-drive / outside-root path
- case variation on Windows
- symlink / junction inside and outside (privilege-gated)
- NUL byte / empty / whitespace input
- long-path policy (no blanket 260-char limit) and ``\\?\\`` prefix equivalence
- scanned root itself and its parent/ancestor
- nonexistent path
- deleted/renamed-after-scan (race-related) scenario
- protected Tier 0 path
- unresolvable/invalid path denied
- internal canonical path does not leak into user-facing output
- CLI- and API-level enforcement of the same boundary
- audit log written for success, denied, and failure attempts
"""

import io
import json
import os
import sys
import tempfile

import pytest
from rich.console import Console
from fastapi.testclient import TestClient

from folder_analyzer.audit import DeletionAuditor
from folder_analyzer.deleter import delete_folders
from folder_analyzer.i18n import I18n
from folder_analyzer.security_guard import (
    GuardStatus,
    canonical_key,
    display_path,
    is_valid_path_input,
    validate_delete_target,
)
from api.main import app

client = TestClient(app)


# --------------------------------------------------------------------------
# Symlink/junction availability (Windows may require privileges/developer mode)
# --------------------------------------------------------------------------

def _can_create_symlink() -> bool:
    try:
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            os.makedirs(src)
            os.symlink(src, os.path.join(d, "lnk"), target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


CAN_SYMLINK = _can_create_symlink()

needs_symlink = pytest.mark.skipif(
    not CAN_SYMLINK, reason="Symlink creation requires privilege/developer mode"
)


# --------------------------------------------------------------------------
# Pure guard behavior
# --------------------------------------------------------------------------

def test_invalid_input_empty_string():
    v = validate_delete_target("")
    assert v.status == GuardStatus.INVALID_INPUT


def test_invalid_input_whitespace():
    v = validate_delete_target("   ")
    assert v.status == GuardStatus.INVALID_INPUT


def test_invalid_input_nul_byte():
    v = validate_delete_target("C:\\foo\x00bar")
    assert v.status == GuardStatus.INVALID_INPUT


def test_invalid_input_non_string():
    assert is_valid_path_input(12345) is False


def test_nonexistent_path_is_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        missing = os.path.join(tmpdir, "does_not_exist")
        v = validate_delete_target(missing)
        assert v.status == GuardStatus.NOT_FOUND


def test_scan_root_cannot_be_deleted():
    with tempfile.TemporaryDirectory() as tmpdir:
        v = validate_delete_target(tmpdir, scan_root=tmpdir)
        assert v.status == GuardStatus.DENIED_ROOT


def test_ancestor_of_scan_root_is_outside_boundary():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        v = validate_delete_target(tmpdir, scan_root=sub)
        assert v.status == GuardStatus.DENIED_CONTAINMENT


def test_child_inside_boundary_is_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        v = validate_delete_target(sub, scan_root=tmpdir)
        assert v.status == GuardStatus.OK
        assert v.canonical


def test_outside_root_denied_containment():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        v = validate_delete_target(b, scan_root=a)
        assert v.status == GuardStatus.DENIED_CONTAINMENT


def test_traversal_escape_denied():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        escape = os.path.join(sub, "..", "..", tmpdir[-7:] or "x", "..", "..")
        escape = os.path.join(tmpdir, "sub", "..", "..")
        v = validate_delete_target(escape, scan_root=tmpdir)
        assert v.status in (GuardStatus.DENIED_CONTAINMENT, GuardStatus.NOT_FOUND)


def test_traversal_inside_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        inpath = os.path.join(tmpdir, "sub", "..", "sub")
        v = validate_delete_target(inpath, scan_root=tmpdir)
        assert v.status == GuardStatus.OK


@pytest.mark.skipif(sys.platform != "win32", reason="case-insensitivity is Windows-specific")
def test_case_variation_on_windows():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        variant = sub.upper()
        v = validate_delete_target(variant, scan_root=tmpdir)
        assert v.status == GuardStatus.OK
        assert canonical_key(variant) == canonical_key(sub)


@pytest.mark.skipif(sys.platform != "win32", reason="extended-length prefix is Windows-specific")
def test_extended_length_prefix_equivalent():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        prefixed = "\\\\?\\" + os.path.abspath(sub)
        assert canonical_key(sub) == canonical_key(prefixed)
        assert validate_delete_target(prefixed, scan_root=tmpdir).status == GuardStatus.OK


@pytest.mark.skipif(sys.platform != "win32", reason="Tier-0/critical paths are Windows-specific")
def test_extended_length_prefix_cannot_bypass_tier0_protection():
    r"""A \\?\-prefixed Tier-0/critical root must be DENIED inside a containing
    scan root. Before the canonicalization fix these returned OK (the check
    compared the raw \\?\-prefixed string against plain C:\... entries).
    """
    targets = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\$Recycle.Bin",
        r"C:\System Volume Information",
        r"C:\Recovery",
        r"C:\PROGRAM FILES",  # case variant of a critical root
    ]
    for raw in targets:
        prefixed = "\\\\?\\" + raw
        v = validate_delete_target(prefixed, scan_root="C:\\")
        assert v.status in (
            GuardStatus.DENIED_CRITICAL,
            GuardStatus.DENIED_PROTECTED,
        ), f"prefixed critical path not blocked: {prefixed} -> {v.status}"


@pytest.mark.skipif(sys.platform != "win32", reason="Tier-0/critical paths are Windows-specific")
def test_plain_critical_path_still_blocked_control():
    """Positive control: the same roots WITHOUT the \\?\\ prefix are still DENIED."""
    for raw in (r"C:\Program Files", r"C:\Windows\System32"):
        v = validate_delete_target(raw, scan_root="C:\\")
        assert v.status in (
            GuardStatus.DENIED_CRITICAL,
            GuardStatus.DENIED_PROTECTED,
        ), f"plain critical path not blocked: {raw}"


def test_no_blanket_260_character_cutoff():
    with tempfile.TemporaryDirectory() as tmpdir:
        long_name = "x" * 300
        fake = os.path.join(tmpdir, long_name)
        v = validate_delete_target(fake, scan_root=tmpdir)
        # A long path we cannot operate on is reported as not-found/deferred,
        # NEVER as a category error based purely on length.
        assert v.status in (GuardStatus.NOT_FOUND, GuardStatus.NOT_RESOLVABLE)
        assert "260" not in v.reason.lower()


def test_protected_tier0_system32():
    v = validate_delete_target(r"C:\Windows\System32", scan_root="C:\\")
    assert v.status == GuardStatus.DENIED_CRITICAL


def test_spaces_and_special_characters_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        weird = os.path.join(tmpdir, "my data (1) [2026] #temp, &stuff")
        os.makedirs(weird)
        v = validate_delete_target(weird, scan_root=tmpdir)
        assert v.status == GuardStatus.OK
        assert v.canonical is not None


def test_display_path_never_leaks_internal_prefix():
    assert "\\\\?\\" not in display_path(r"C:\Temp\some\folder")
    key = canonical_key(r"C:\Temp\some\folder")
    assert key is None or "\\\\?\\" not in key


@needs_symlink
def test_symlink_inside_boundary_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = os.path.join(tmpdir, "real")
        os.makedirs(target_dir)
        link = os.path.join(tmpdir, "link_to_real")
        os.symlink(target_dir, link, target_is_directory=True)
        v = validate_delete_target(link, scan_root=tmpdir)
        assert v.status == GuardStatus.OK


@needs_symlink
def test_symlink_escape_is_denied():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        link = os.path.join(a, "escape")
        os.symlink(b, link, target_is_directory=True)
        v = validate_delete_target(link, scan_root=a)
        assert v.status == GuardStatus.DENIED_CONTAINMENT


# --------------------------------------------------------------------------
# CLI-level enforcement (deleter.py)
# --------------------------------------------------------------------------

def _run_deleter(paths, scan_root, audit_log, monkeypatch):
    sent = []
    monkeypatch.setattr("folder_analyzer.deleter.send2trash", lambda p: sent.append(p))
    monkeypatch.setattr("folder_analyzer.deleter.Confirm", _FakeConfirm(True))
    console = Console(file=io.StringIO())
    deleted = delete_folders(
        paths, I18n("en"), console,
        stats={p: (0, 0) for p in paths},
        protected=[scan_root] if scan_root else [],
        scan_root=scan_root,
        audit_log=audit_log,
    )
    return deleted, sent


class _FakeConfirm:
    def __init__(self, result):
        self._result = result

    def ask(self, *args, **kwargs):
        return self._result


def test_deleter_blocks_outside_same_guard_and_audits(monkeypatch):
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        audit = os.path.join(a, "audit.jsonl")
        deleted, sent = _run_deleter([b], a, audit, monkeypatch)
        assert deleted == 0
        assert sent == []
        lines = [json.loads(x) for x in open(audit, encoding="utf-8") if x.strip()]
        assert lines and lines[0]["status"] == "denied"
        assert "\\\\?\\" not in lines[0]["path"]


def test_deleter_success_writes_audit(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        child = os.path.join(tmpdir, "child")
        os.makedirs(child)
        audit = os.path.join(tmpdir, "audit.jsonl")
        deleted, sent = _run_deleter([child], tmpdir, audit, monkeypatch)
        assert deleted == 1
        assert sent == [child]
        lines = [json.loads(x) for x in open(audit, encoding="utf-8") if x.strip()]
        assert lines[0]["status"] == "success"
        assert lines[0]["path"] == display_path(child)
        assert "\\\\?\\" not in lines[0]["path"]


def test_audit_log_append_only_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        log = os.path.join(tmpdir, "a.jsonl")
        auditor = DeletionAuditor(log)
        auditor.record(status="denied", original=r"C:\x", reason="r")
        auditor.record(status="success", original=r"C:\y", success=True)
        lines = [json.loads(x) for x in open(log, encoding="utf-8") if x.strip()]
        assert len(lines) == 2
        assert lines[0]["status"] == "denied"
        assert lines[1]["success"] is True
        assert "timestamp" in lines[0]
        assert lines[0]["path"] == r"C:\x"


# --------------------------------------------------------------------------
# API-level enforcement
# --------------------------------------------------------------------------

def _reset_state():
    app.state.last_scan_root = None


def test_api_delete_nul_byte_is_400():
    _reset_state()
    response = client.post("/api/delete", json={"paths": ["C:\\x\x00y"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INVALID_PATH"


def test_api_delete_empty_path_is_400():
    _reset_state()
    response = client.post("/api/delete", json={"paths": ["   "]})
    assert response.status_code == 400


def test_api_delete_outside_scan_blocked():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        client.post("/api/scan", json={"path": a})
        response = client.post("/api/delete", json={"paths": [b]})
        assert response.status_code == 200
        data = response.json()
        assert data["total_blocked"] == 1
        assert data["total_deleted"] == 0
        assert "\\\\?\\" not in response.text


def test_api_delete_root_and_ancestor_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        client.post("/api/scan", json={"path": sub})
        parent = os.path.dirname(tmpdir)
        response = client.post("/api/delete", json={"paths": [tmpdir, parent]})
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 0
        assert data["total_blocked"] == 2


def test_api_delete_race_target_removed_is_failure_not_throw():
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim")
        os.makedirs(victim)
        client.post("/api/scan", json={"path": tmpdir})
        os.rmdir(victim)  # target disappears between scan and delete
        response = client.post("/api/delete", json={"paths": [victim]})
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 0
        assert len(data["deleted"]) == 1
        assert data["deleted"][0]["success"] is False
        assert data["deleted"][0]["status"] == "failure"


def test_api_delete_child_inside_boundary_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        child = os.path.join(tmpdir, "child")
        os.makedirs(child)
        client.post("/api/scan", json={"path": tmpdir})
        response = client.post("/api/delete", json={"paths": [child]})
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 1
        assert data["deleted"][0]["success"] is True
        assert not os.path.exists(child)
        assert "\\\\?\\" not in data["deleted"][0]["path"]


def test_api_delete_protected_root_still_blocked():
    _reset_state()
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        client.post("/api/scan", json={"path": sub})
        response = client.post("/api/delete", json={"paths": [tmpdir]})
        assert response.status_code == 200
        assert response.json()["total_blocked"] == 1