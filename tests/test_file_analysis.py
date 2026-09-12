"""Phase 3 — per-file analysis, zero-extra-syscall metadata, bounded retention.

Covers:
- FileEntry metadata correctness (path/filename/extension/size/timestamps/attrs).
- Zero-extra-syscall: one ``stat()`` per file, one ``scandir()`` per folder.
- Retention boundaries: per-folder cap, global budget, eviction priority order
  (non-safe -> representative -> largest -> path tie-break).
- The 100%-analyzed invariant: ``files_analyzed`` == all accessible files even
  when ``records_retained`` < files_analyzed because of eviction.
- On-demand re-analysis of evicted folders.
"""

import os
import tempfile

import pytest

from folder_analyzer.scanner import Scanner
from folder_analyzer.engine.enums import (
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from folder_analyzer.engine.models import Assessment, FileEntry
from folder_analyzer.engine.retention import (
    RetainedFileStore,
    RetentionConfig,
    select_folder_records,
)


def _make_entry(path: str, size: int, assessment=None, category: str = "unknown") -> FileEntry:
    name = os.path.basename(path)
    _, ext = os.path.splitext(name)
    return FileEntry(
        path=path,
        filename=name,
        extension=ext.lower(),
        size=size,
        created_ts=1.0,
        modified_ts=1.0,
        accessed_ts=1.0,
        attributes={"st_mode": 0, "st_ino": 1, "st_nlink": 1, "is_symlink": False},
        assessment=assessment,
        category=category,
    )


def _make_tree(n_files=2, n_subdirs=1, name_prefix="file", content="x"):
    """Root with n_files direct files and n_subdirs subdirs each with n_files."""
    tmpdir = tempfile.mkdtemp()
    for i in range(n_files):
        with open(os.path.join(tmpdir, f"{name_prefix}{i}.txt"), "w") as f:
            f.write(content)
    for s in range(n_subdirs):
        sub = os.path.join(tmpdir, f"sub{s}")
        os.makedirs(sub)
        for i in range(n_files):
            with open(os.path.join(sub, f"{name_prefix}{i}.log"), "w") as f:
                f.write(content)
    return tmpdir


# ---------------------------------------------------------------------------
# Metadata correctness (Level 1 = metadata only, no classification)
# ---------------------------------------------------------------------------

def test_file_entry_metadata_extracted():
    import os as _os
    tmpdir = _make_tree(n_files=2, n_subdirs=0)
    try:
        scanner = Scanner(max_workers=2)
        scanner.scan(tmpdir)
        agg = scanner.aggregation_for(tmpdir)
        assert agg.files_analyzed == 2
        records = scanner.records_for(tmpdir)
        by_name = {r.filename: r for r in records}
        assert set(by_name) == {"file0.txt", "file1.txt"}
        record = by_name["file0.txt"]
        assert record.path == os.path.join(tmpdir, "file0.txt")
        assert record.extension == ".txt"
        assert record.size == 1
        assert record.created_ts is not None and record.created_ts > 0
        assert record.modified_ts is not None and record.modified_ts > 0
        assert record.accessed_ts is not None and record.accessed_ts > 0
        assert set(record.attributes) == {
            "st_mode", "st_ino", "st_nlink", "is_symlink"
        }
        assert record.assessment is None
        assert record.category == "unknown"
    finally:
        _shutil_rmtree(tmpdir)


# ---------------------------------------------------------------------------
# Zero-extra-syscall: one scandir per folder, one stat per file
# ---------------------------------------------------------------------------

def test_zero_extra_syscalls_metadata(tmp_path):
    import folder_analyzer.scanner as scanner_mod

    tmpdir = str(tmp_path)
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.log").write_text("bb")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("ccc")

    real_scandir = scanner_mod.os.scandir
    calls = {"scandir": 0, "stat": 0}

    class CountingEntry:
        def __init__(self, real):
            self._real = real
            self.name = real.name
            self.path = real.path

        def stat(self, follow_symlinks=True):
            calls["stat"] += 1
            return self._real.stat(follow_symlinks=follow_symlinks)

        def is_file(self, follow_symlinks=True):
            return self._real.is_file(follow_symlinks=follow_symlinks)

        def is_dir(self, follow_symlinks=True):
            return self._real.is_dir(follow_symlinks=follow_symlinks)

        def is_symlink(self):
            return self._real.is_symlink()

    def counting_scandir(path):
        calls["scandir"] += 1
        return (CountingEntry(e) for e in real_scandir(path))

    try:
        scanner_mod.os.scandir = counting_scandir  # type: ignore[assignment]
        scanner = Scanner(max_workers=1)
        scanner.scan(tmpdir)
    finally:
        scanner_mod.os.scandir = real_scandir

    assert calls["scandir"] == 2          # root + sub (no extra re-scans)
    assert calls["stat"] == 3             # exactly one per file -> zero extra syscalls
    assert scanner.records_retained == 3


# ---------------------------------------------------------------------------
# Retention boundaries (caps + priorities)
# ---------------------------------------------------------------------------

def test_per_folder_cap_is_configurable():
    tmpdir = _make_tree(n_files=5, n_subdirs=0, content="x" * 10)
    try:
        scanner = Scanner(max_workers=1, retention=RetentionConfig(
            global_budget=100, per_folder_cap=3))
        scanner.scan(tmpdir)
        records = scanner.records_for(tmpdir)
        assert len(records) == 3
        assert sorted(r.size for r in records) == [10, 10, 10]
    finally:
        _shutil_rmtree(tmpdir)


def test_global_budget_is_configurable():
    tmpdir = _make_tree(n_files=5, n_subdirs=2, content="x")
    try:
        scanner = Scanner(max_workers=1, retention=RetentionConfig(
            global_budget=3, per_folder_cap=2))
        scanner.scan(tmpdir)
        assert scanner.records_retained == 3
    finally:
        _shutil_rmtree(tmpdir)


def test_cap_zero_retains_nothing():
    tmpdir = _make_tree(n_files=3, n_subdirs=0)
    try:
        scanner = Scanner(max_workers=1, retention=RetentionConfig(
            global_budget=100, per_folder_cap=0))
        scanner.scan(tmpdir)
        assert scanner.records_retained == 0
        assert scanner.aggregation_for(tmpdir).records_retained == 0
    finally:
        _shutil_rmtree(tmpdir)


def test_largest_files_retained_before_smaller():
    tmpdir = _make_tree(n_files=10, n_subdirs=0)
    try:
        # Make sizes distinct so priority order is observable.
        paths = sorted(
            os.path.join(tmpdir, p) for p in os.listdir(tmpdir)
        )
        for i, p in enumerate(paths):
            with open(p, "w") as f:
                f.write("x" * (i * 10))
        scanner = Scanner(max_workers=1, retention=RetentionConfig(
            global_budget=4, per_folder_cap=10))
        scanner.scan(tmpdir)
        retained = scanner.records_for(tmpdir)
        assert len(retained) == 4
        reps = [r for r in retained if r.is_representative]
        non_reps = [r for r in retained if not r.is_representative]
        assert len(reps) == 1          # the sampler exception survives eviction
        assert reps[0].size == 0       # ...even though it is the smallest file
        assert sorted(r.size for r in non_reps) == [70, 80, 90]  # 4 total = rep + 3 largest
    finally:
        _shutil_rmtree(tmpdir)


def test_non_safe_records_survive_eviction_over_largest():
    """Priority 1, the relevance hook: REVIEW/KEEP records beat big files.

    Inert in Phase 3 (no classifier attaches assessments); proven here with
    synthetic Assessments so it becomes live automatically in Phase 5.
    """
    keep = Assessment(impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
                      reason_key="keep",
                      recommendation=DeletionRecommendation.KEEP)
    store = RetainedFileStore(RetentionConfig(global_budget=2, per_folder_cap=5))
    entries = [
        _make_entry("C:\\f\\big1.bin", 1000),
        _make_entry("C:\\f\\big2.bin", 900),
        _make_entry("C:\\f\\small1.bin", 10, assessment=keep),
        _make_entry("C:\\f\\small2.bin", 10, assessment=keep),
    ]
    store.add_entries("C:\\f", entries)
    retained_paths = {r.path for r in store.records_for_folder("C:\\f")}
    assert retained_paths == {"C:\\f\\small1.bin", "C:\\f\\small2.bin"}


def test_representative_sample_kept_even_if_smallest():
    """One representative per (folder, category) beats raw size."""
    store = RetainedFileStore(RetentionConfig(global_budget=1, per_folder_cap=3))
    store.add_entries("C:\\f", [
        _make_entry("C:\\f\\small_first.txt", 1),
        _make_entry("C:\\f\\huge.bin", 100),
        _make_entry("C:\\f\\mid.txt", 50),
    ])
    retained = store.records_for_folder("C:\\f")
    assert len(retained) == 1
    assert retained[0].path == "C:\\f\\small_first.txt"
    assert retained[0].is_representative is True


def test_representative_marked_in_selection():
    selected = select_folder_records(
        [(_make_entry("C:\\f\\b.bin", 5)),
         (_make_entry("C:\\f\\a.bin", 3))], per_folder_cap=10)
    reps = [r for r in selected if r.is_representative]
    assert len(reps) == 1
    assert reps[0].path == "C:\\f\\b.bin"  # first in encounter order


def test_representative_one_per_distinct_category_per_folder():
    """Multi-category ordering: at least one rep per category survives, then
    the remaining cap is filled by the largest non-representatives.

    Uses the FileEntry-level entry point because Phase 3's scanner always tags
    the single "unknown" category; real categories arrive in Phase 5.
    """
    store = RetainedFileStore(RetentionConfig(global_budget=10, per_folder_cap=4))
    store.add_entries("C:\\f", [
        _make_entry("C:\\f\\docs_a.pdf", 1, category="documents"),
        _make_entry("C:\\f\\docs_b.pdf", 2, category="documents"),
        _make_entry("C:\\f\\media_a.mp4", 3, category="media"),
        _make_entry("C:\\f\\media_b.mp4", 4, category="media"),
        _make_entry("C:\\f\\code_a.py", 5, category="code"),
        _make_entry("C:\\f\\code_b.py", 6, category="code"),
    ])
    retained = store.records_for_folder("C:\\f")
    assert len(retained) == 4  # cap 4 = 3 category reps + 1 largest fill

    reps = [r for r in retained if r.is_representative]
    assert {r.category for r in reps} == {"documents", "media", "code"}
    assert len(reps) == 3  # exactly one representative per distinct category
    # The one non-representative slot goes to the single largest file.
    non_reps = [r for r in retained if not r.is_representative]
    assert [r.size for r in non_reps] == [6]


def test_category_reps_all_kept_when_cap_equals_category_count():
    """With cap == number of categories, no size fill happens and every
    category still has exactly one representative (smallest files included)."""
    store = RetainedFileStore(RetentionConfig(global_budget=10, per_folder_cap=2))
    store.add_entries("C:\\f", [
        _make_entry("C:\\f\\tiny_a.bin", 1, category="a"),
        _make_entry("C:\\f\\huge_a.bin", 9_000, category="a"),
        _make_entry("C:\\f\\tiny_b.bin", 2, category="b"),
        _make_entry("C:\\f\\huge_b.bin", 9_500, category="b"),
    ])
    retained = store.records_for_folder("C:\\f")
    assert len(retained) == 2
    assert {r.category for r in retained} == {"a", "b"}
    assert all(r.is_representative for r in retained)
    # Encounter order picks the first of each category, not the largest.
    assert {r.filename for r in retained} == {"tiny_a.bin", "tiny_b.bin"}


# ---------------------------------------------------------------------------
# 100%-analyzed invariant (eviction never reduces files_analyzed)
# ---------------------------------------------------------------------------

def test_files_analyzed_equals_total_even_under_eviction():
    tmpdir = _make_tree(n_files=5, n_subdirs=2, content="x")
    try:
        total_expected = 5 + 2 * 5  # root + 2 subdirs x 5
        scanner = Scanner(max_workers=1, retention=RetentionConfig(
            global_budget=2, per_folder_cap=1))
        scanner.scan(tmpdir)
        result = scanner.scan_result()
        assert result.files_analyzed == total_expected
        assert result.records_retained == 2
        assert result.records_retained < result.files_analyzed
        # Every folder reports its full analyzed count too:
        for agg in result.per_folder.values():
            assert agg.files_analyzed >= 1
        assert sum(a.files_analyzed for a in result.per_folder.values()) == total_expected
    finally:
        _shutil_rmtree(tmpdir)


def test_aggregation_shape_is_defined_and_zero_until_phase5():
    tmpdir = _make_tree(n_files=2, n_subdirs=1)
    try:
        scanner = Scanner(max_workers=1)
        scanner.scan(tmpdir)
        agg = scanner.aggregation_for(tmpdir)
        assert agg.files_analyzed == 2
        assert agg.unknown_count == agg.files_analyzed  # Phase 3: all unclassified
        assert set(agg.by_recommendation) == set(DeletionRecommendation)
        assert all(v == 0 for v in agg.by_recommendation.values())
        assert set(agg.by_impact) == set(SystemImpact)
        assert all(v == 0 for v in agg.by_impact.values())
        assert set(agg.by_confidence) == set(ConfidenceLevel)
        assert all(v == 0 for v in agg.by_confidence.values())
        assert agg.protected_count == 0 and agg.protected_size == 0
        assert agg.user_data_count == 0 and agg.user_data_size == 0
        assert agg.app_ids == {}
    finally:
        _shutil_rmtree(tmpdir)


# ---------------------------------------------------------------------------
# On-demand re-analysis (drill-down into an evicted folder)
# ---------------------------------------------------------------------------

def test_evicted_folder_is_rescanned_on_demand():
    tmpdir = _make_tree(n_files=5, n_subdirs=2, content="x")
    try:
        scanner = Scanner(max_workers=1, retention=RetentionConfig(
            global_budget=1, per_folder_cap=5))
        scanner.scan(tmpdir)
        # Two subdirs + root, budget 1 -> at least one folder fully evicted.
        evicted = [p for p in (tmpdir, os.path.join(tmpdir, "sub0"),
                               os.path.join(tmpdir, "sub1")) if scanner.is_evicted(p)]
        assert evicted, "budget must evict at least one folder"
        target = evicted[0]
        first = scanner.records_for(target)
        assert len(first) == 5
        # Now delete one file in that folder; the fresh re-read must reflect it.
        os.remove(os.path.join(target, "file0.txt"))
        second = scanner.records_for(target)
        assert len(second) == 4
        assert all(r.filename != "file0.txt" for r in second)
    finally:
        _shutil_rmtree(tmpdir)


def test_evicted_folder_rescan_scans_only_that_folder(tmp_path):
    """Drill-down re-analysis must re-read the evicted folder alone, not the tree.

    Instruments os.scandir/entry.stat during the records_for() call only:
    exactly one scandir (the target folder) and one stat per file *in that
    folder* — a whole-tree re-scan would show 3 scandir and 12 stat here.
    """
    import folder_analyzer.scanner as scanner_mod

    tmpdir = str(tmp_path)
    for i in range(2):
        (tmp_path / f"r{i}.txt").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    for i in range(5):
        (sub / f"s{i}.txt").write_text("x")

    scanner = Scanner(max_workers=1, retention=RetentionConfig(
        global_budget=1, per_folder_cap=10))
    scanner.scan(tmpdir)

    evicted = [p for p in (tmpdir, str(sub)) if scanner.is_evicted(p)]
    assert len(evicted) == 1, "budget 1 across 2 folders must evict exactly one"
    target = evicted[0]
    target_files = [
        n for n in os.listdir(target)
        if os.path.isfile(os.path.join(target, n))
    ]

    real_scandir = scanner_mod.os.scandir
    calls = {"scandir": 0, "stat": 0}

    class CountingEntry:
        def __init__(self, real):
            self._real = real
            self.name = real.name
            self.path = real.path

        def stat(self, follow_symlinks=True):
            calls["stat"] += 1
            return self._real.stat(follow_symlinks=follow_symlinks)

        def is_file(self, follow_symlinks=True):
            return self._real.is_file(follow_symlinks=follow_symlinks)

        def is_dir(self, follow_symlinks=True):
            return self._real.is_dir(follow_symlinks=follow_symlinks)

        def is_symlink(self):
            return self._real.is_symlink()

    def counting_scandir(path):
        calls["scandir"] += 1
        return (CountingEntry(e) for e in real_scandir(path))

    try:
        scanner_mod.os.scandir = counting_scandir  # type: ignore[assignment]
        fresh = scanner.records_for(target)
    finally:
        scanner_mod.os.scandir = real_scandir

    assert len(fresh) == len(target_files)
    assert {r.filename for r in fresh} == set(target_files)
    assert calls["scandir"] == 1            # only the target folder
    assert calls["stat"] == len(target_files)  # only that folder's files


def _shutil_rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)