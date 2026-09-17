"""Tests for the scanner module."""

import os
import tempfile
import pytest
from folder_analyzer.engine.enums import DeletionRecommendation
from folder_analyzer.scanner import Scanner, FolderInfo, sort_folders_by_size


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "sub1"))
        os.makedirs(os.path.join(tmpdir, "sub2"))
        os.makedirs(os.path.join(tmpdir, "sub1", "deep"))

        for name in ["file1.txt", "file2.txt"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("x" * 1000)

        with open(os.path.join(tmpdir, "sub1", "file3.txt"), "w") as f:
            f.write("y" * 500)

        with open(os.path.join(tmpdir, "sub1", "deep", "file4.txt"), "w") as f:
            f.write("z" * 2000)

        yield tmpdir


def test_scanner_basic(tmp_dir):
    scanner = Scanner(max_workers=2)
    result = scanner.scan(tmp_dir)

    assert isinstance(result, FolderInfo)
    assert result.path == os.path.normpath(tmp_dir)
    assert result.file_count == 4
    assert result.total_size == 1000 * 2 + 500 + 2000
    assert len(result.children) == 2


def test_scanner_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        scanner = Scanner(max_workers=2)
        result = scanner.scan(tmpdir)

        assert result.file_count == 0
        assert result.total_size == 0
        assert len(result.children) == 0


def test_scanner_nested_structure(tmp_dir):
    scanner = Scanner(max_workers=4)
    result = scanner.scan(tmp_dir)

    sub1 = next(c for c in result.children if c.name == "sub1")
    assert sub1.file_count == 2
    assert sub1.total_size == 500 + 2000
    assert len(sub1.children) == 1
    assert sub1.children[0].name == "deep"


def test_sort_folders_by_size(tmp_dir):
    scanner = Scanner(max_workers=2)
    result = scanner.scan(tmp_dir)
    top = sort_folders_by_size(result, top_n=5)

    assert len(top) > 0
    assert top[0].total_size >= top[1].total_size


def test_sort_folders_by_size_excludes_scan_root(tmp_dir):
    scanner = Scanner(max_workers=2)
    result = scanner.scan(tmp_dir)
    top = sort_folders_by_size(result, top_n=50)

    assert all(f.path != result.path for f in top), "scan root must not appear in top folders"


def test_sort_folders_by_size_includes_children(tmp_dir):
    scanner = Scanner(max_workers=2)
    result = scanner.scan(tmp_dir)
    top = sort_folders_by_size(result, top_n=50)

    assert len(top) == 2  # sub1 and sub1/deep (sub2 is empty -> excluded)


def test_to_dict(tmp_dir):
    scanner = Scanner(max_workers=2)
    result = scanner.scan(tmp_dir)
    d = result.to_dict()

    assert "path" in d
    assert "total_size" in d
    assert "children" in d
    assert isinstance(d["children"], list)


def test_scanner_progress_callback(tmp_dir):
    scanner = Scanner(max_workers=2)
    progress_calls = []

    def on_progress(folders, files):
        progress_calls.append((folders, files))

    scanner.scan(tmp_dir, on_progress=on_progress)
    assert len(progress_calls) > 0


def test_scanner_nested_only_folder_stays_review_first(tmp_dir):
    """TASK 5B regression lock: a real scanner pass on a nested-only folder.

    The parent holds 0 DIRECT bytes (all content lives in its subfolder), so
    the scanner builds an EMPTY direct composition and the derived folder
    recommendation must be REVIEW_FIRST (reason_key=``r6_review_first``), even
    though the parent's recursive content is 100% disposable. The disposable
    child folder (with positive direct disposable evidence) stays
    SAFE_TO_DELETE (reason_key=``r5_safe_to_delete``).
    """
    nested = os.path.join(tmp_dir, "nested_only")
    cache = os.path.join(nested, "cache")
    os.makedirs(cache, exist_ok=True)
    for name in ["a.tmp", "b.tmp", "c.tmp"]:
        with open(os.path.join(cache, name), "w") as f:
            f.write("x" * 10)

    scanner = Scanner(max_workers=2)
    scanner.scan(nested)
    result = scanner.scan_result()

    parent = result.per_folder[os.path.normpath(nested)]
    child = result.per_folder[os.path.normpath(cache)]

    assert parent.files_analyzed == 0
    assert parent.composition.total_bytes == 0
    assert parent.assessment.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert parent.assessment.reason_key == "r6_review_first"

    assert child.files_analyzed == 3
    assert child.composition.total_bytes == 30
    assert child.assessment.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert child.assessment.reason_key == "r5_safe_to_delete"
