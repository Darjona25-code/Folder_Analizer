"""Tests for the deletion module."""

import io
import os
import sys
import tempfile

import pytest
from rich.console import Console

from folder_analyzer.deleter import delete_folders, get_folder_size, is_protected_path
from folder_analyzer.i18n import I18n


def test_get_folder_size_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "a", "b"))
        with open(os.path.join(tmpdir, "a", "f1.txt"), "w") as f:
            f.write("x" * 100)
        with open(os.path.join(tmpdir, "a", "b", "f2.txt"), "w") as f:
            f.write("y" * 200)

        size, count = get_folder_size(os.path.join(tmpdir, "a"))
        assert size == 300
        assert count == 2


def test_get_folder_size_deep_no_recursion():
    """A deep tree must not raise RecursionError (iterative traversal)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        depth = 90
        path = tmpdir
        for _ in range(depth):
            path = os.path.join(path, "d")
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "leaf.txt"), "w") as f:
            f.write("z" * 42)

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(60)  # far below 90 -> a recursive impl would blow up
        try:
            size, count = get_folder_size(tmpdir)
        finally:
            sys.setrecursionlimit(old_limit)

        assert count == 1
        assert size == 42


def test_is_protected_path_exact_match():
    assert is_protected_path(r"C:\Data\Scan", [r"C:\Data\Scan"]) is True


def test_is_protected_path_ancestor():
    assert is_protected_path(r"C:\Data", [r"C:\Data\Scan"]) is True


def test_is_protected_path_child_is_free():
    assert is_protected_path(r"C:\Data\Scan\sub", [r"C:\Data\Scan"]) is False


def test_is_protected_path_unrelated():
    assert is_protected_path(r"C:\Other\thing", [r"C:\Data\Scan"]) is False


def test_delete_folders_blocks_protected_root(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        child = os.path.join(tmpdir, "child")
        os.makedirs(child)

        sent = []
        monkeypatch.setattr("folder_analyzer.deleter.send2trash", lambda p: sent.append(p))

        console = Console(file=io.StringIO())
        deleted = delete_folders(
            [tmpdir], I18n("en"), console,
            stats={tmpdir: (0, 0)}, protected=[tmpdir],
        )

        assert deleted == 0
        assert sent == []
        assert "root" in console.file.getvalue() or "root" in console.file.getvalue().lower()


def test_delete_folders_deletes_safe_child(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        child = os.path.join(tmpdir, "child")
        os.makedirs(child)
        with open(os.path.join(child, "a.txt"), "w") as f:
            f.write("x" * 10)

        sent = []
        monkeypatch.setattr("folder_analyzer.deleter.send2trash", lambda p: sent.append(p))
        monkeypatch.setattr("folder_analyzer.deleter.Confirm", _FakeConfirm(True))

        console = Console(file=io.StringIO())
        deleted = delete_folders(
            [child], I18n("en"), console,
            stats={child: (10, 1)}, protected=[tmpdir],
        )

        assert deleted == 1
        assert sent == [child]


class _FakeConfirm:
    def __init__(self, result):
        self._result = result

    def ask(self, *args, **kwargs):
        return self._result