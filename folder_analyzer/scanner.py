"""Multi-threaded disk scanner for Folder Analyzer.

Phase 5: Level-1 path classification + folder composition are now wired into
the scan path. Per-file ``Assessment`` objects are produced by the classifier
during traversal and folded, per folder, into countable tallies (100% of the
accessible files, roadmap §8) and, for the RETAINED subset, attached to the
``FileEntry`` records so the retention non-SAFE priority (roadmap §9) is live.

Memory discipline is preserved:

- every accessible file is classified (path-level only, no file I/O) for the
  per-folder counts and byte composition;
- ``Assessment`` objects are held only transiently per folder and, after the
  retention store keeps its bounded subset, released;
- the per-folder tallies kept for the whole scan are counters (ints), not
  per-file objects.

``files_analyzed`` always equals 100% of the accessible files; eviction only
reduces ``records_retained``. Folder-level ``Assessment`` (derived via roadmap
§11 composition) never overrides item-level authority (I10).
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .engine.classifier import (
    ScanAssessment,
    assessment_from_scan_record,
    classify_scan,
)
from .engine.enums import (
    CompositionBucket,
    ConfidenceLevel,
    DeletionRecommendation,
    SystemImpact,
)
from .engine.models import FileEntry, FolderAggregation, FolderComposition, ScanResult
from .engine.kb import prepare_scan_folder
from .engine.recommender import derive_folder_recommendation
from .engine.retention import (
    RetainedFileStore,
    RetentionConfig,
    select_folder_raw,
)

ProgressCallback = Callable[[int, int], None]


class ScanCancellation:
    """Core-side cancellation token for ``Scanner.scan`` (Phase 8).

    Thread-safe. ``cancel()`` may be called from any thread while a scan runs;
    the scanner checks ``is_cancelled`` at folder granularity (and at least
    once every ``_CANCEL_CHECK_EVERY`` files inside a folder) and stops as soon
    as the check fires, returning the partial tree. A cancelled scan result is
    explicit: ``scan_result().cancelled`` is True and represents only the
    folders already completed at cancel time.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


_CANCEL_CHECK_EVERY = 4096


@dataclass
class FolderInfo:
    path: str
    name: str
    total_size: int = 0
    file_count: int = 0
    folder_count: int = 0
    direct_size: int = 0
    children: list["FolderInfo"] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "total_size": self.total_size,
            "file_count": self.file_count,
            "folder_count": self.folder_count,
            "direct_size": self.direct_size,
            "children": [c.to_dict() for c in self.children],
            "error": self.error,
        }


@dataclass
class _FolderTally:
    """Classification counters for one folder's DIRECT analyzed files.

    Counters only — bounded, cheap, kept for the whole scan to fold into
    ``FolderAggregation`` at ``scan_result()``.
    """

    by_impact: Dict[SystemImpact, int] = field(
        default_factory=lambda: {i: 0 for i in SystemImpact}
    )
    by_recommendation: Dict[DeletionRecommendation, int] = field(
        default_factory=lambda: {r: 0 for r in DeletionRecommendation}
    )
    by_confidence: Dict[ConfidenceLevel, int] = field(
        default_factory=lambda: {c: 0 for c in ConfidenceLevel}
    )
    protected_count: int = 0
    protected_size: int = 0
    unknown_count: int = 0
    unknown_size: int = 0
    user_data_count: int = 0
    user_data_size: int = 0
    app_ids: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    not_resolvable_count: int = 0
    disposable_bytes: int = 0
    user_value_bytes: int = 0
    protected_critical_bytes: int = 0
    known_non_disposable_bytes: int = 0
    unknown_bytes: int = 0


def _bump(tally: _FolderTally, size: int, rec: ScanAssessment) -> None:
    """Fold one classified file into the folder tally (no per-file retention)."""
    tally.by_impact[rec.impact] += 1
    tally.by_recommendation[rec.recommendation] += 1
    tally.by_confidence[rec.confidence] += 1
    if rec.bucket is CompositionBucket.DISPOSABLE:
        tally.disposable_bytes += size
    elif rec.bucket is CompositionBucket.USER_VALUE:
        tally.user_value_bytes += size
    elif rec.bucket is CompositionBucket.PROTECTED_CRITICAL:
        tally.protected_critical_bytes += size
    elif rec.bucket is CompositionBucket.KNOWN_NON_DISPOSABLE:
        tally.known_non_disposable_bytes += size
    else:
        tally.unknown_bytes += size
        tally.unknown_count += 1
        tally.unknown_size += size
    if rec.bucket is CompositionBucket.PROTECTED_CRITICAL:
        tally.protected_count += 1
        tally.protected_size += size
    if rec.reason_key == "not_resolvable":
        tally.not_resolvable_count += 1
    if rec.is_user_data:
        tally.user_data_count += 1
        tally.user_data_size += size
    if rec.app_id is not None:
        tally.app_ids[rec.app_id] = tally.app_ids.get(rec.app_id, 0) + 1
    tally.by_category[rec.detected_category or "unknown"] = (
        tally.by_category.get(rec.detected_category or "unknown", 0) + size
    )


class Scanner:
    def __init__(
        self,
        max_workers: int = 16,
        retention: Optional[RetentionConfig] = None,
    ):
        self.max_workers = max_workers
        self._retention_config = retention or RetentionConfig()
        self._store = RetainedFileStore(self._retention_config)
        self._lock = threading.Lock()
        self._scanned_folders = 0
        self._scanned_files = 0
        self._inaccessible = 0
        self._on_progress: Optional[ProgressCallback] = None
        self._scan_tree: Optional[FolderInfo] = None
        self._tallies: Dict[str, _FolderTally] = {}
        self._cancellation: Optional[ScanCancellation] = None
        self._cancelled = False

    def scan(
        self,
        root_path: str,
        on_progress: Optional[ProgressCallback] = None,
        cancellation: Optional[ScanCancellation] = None,
    ) -> FolderInfo:
        self._scanned_folders = 0
        self._scanned_files = 0
        self._inaccessible = 0
        self._on_progress = on_progress
        self._tallies = {}
        self._cancellation = cancellation
        self._cancelled = False

        root_path = os.path.normpath(root_path)
        root_info = FolderInfo(
            path=root_path,
            name=os.path.basename(root_path) or root_path,
        )
        self._scan_tree = root_info

        self._scan_folder(root_info, root_path, use_threads=True)
        return root_info

    def _scan_folder(self, info: FolderInfo, path: str, use_threads: bool = True):
        if self._is_cancelled():
            return
        try:
            entries = list(os.scandir(path))
        except (PermissionError, OSError) as e:
            info.error = str(e)
            with self._lock:
                self._scanned_folders += 1
                self._report_progress()
            return

        subdirs: List[os.DirEntry] = []
        pending: List[Tuple[os.DirEntry, os.stat_result]] = []
        assessments: "Dict[str, ScanAssessment]" = {}
        tally = _FolderTally()
        ctx = prepare_scan_folder(path)
        inspected = 0
        for entry in entries:
            if inspected % _CANCEL_CHECK_EVERY == 0 and self._is_cancelled():
                return
            inspected += 1
            try:
                if entry.is_file(follow_symlinks=False):
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except (OSError, PermissionError):
                        with self._lock:
                            self._inaccessible += 1
                        continue
                    # Cheap pair during traversal; the retention store builds
                    # FileEntry objects only for the kept (RETAINED) subset.
                    pending.append((entry, st))
                    info.direct_size += st.st_size
                    info.file_count += 1
                    try:
                        rec = classify_scan(
                            entry.path, filename=entry.name, _ctx=ctx,
                        )
                    except Exception:
                        # Classification must never break the scan: degrade to
                        # the NOT_RESOLVABLE pipeline (UNKNOWN/REVIEW_FIRST/LOW).
                        rec = classify_scan(
                            entry.path, filename=entry.name,
                            not_resolvable=True, _ctx=ctx,
                        )
                    assessments[entry.path] = rec
                    _bump(tally, st.st_size, rec)
                    with self._lock:
                        self._scanned_files += 1
                elif entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry)
            except (PermissionError, OSError):
                continue

        with self._lock:
            self._store.record_folder(
                os.path.normpath(path), pending, assessments=assessments,
            )
            self._tallies[os.path.normpath(path)] = tally
        pending.clear()
        assessments.clear()

        if subdirs and use_threads and len(subdirs) > 4:
            self._scan_with_threads(info, subdirs)
        else:
            for subdir in subdirs:
                child = FolderInfo(
                    path=subdir.path,
                    name=subdir.name,
                )
                self._scan_folder(child, subdir.path, use_threads=False)
                info.children.append(child)
                info.folder_count += 1 + child.folder_count
                info.file_count += child.file_count

        info.total_size = info.direct_size + sum(
            c.total_size for c in info.children
        )

        with self._lock:
            self._scanned_folders += 1
            self._report_progress()

    def _scan_with_threads(self, parent_info: FolderInfo, subdirs: list):
        child_map = {}
        futures = {}

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(subdirs))) as executor:
            for subdir in subdirs:
                child = FolderInfo(
                    path=subdir.path,
                    name=subdir.name,
                )
                child_map[subdir.path] = child
                futures[executor.submit(self._scan_folder, child, subdir.path, False)] = subdir.path

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass

        for subdir in subdirs:
            child = child_map[subdir.path]
            parent_info.children.append(child)
            parent_info.folder_count += 1 + child.folder_count
            parent_info.file_count += child.file_count

    def _report_progress(self):
        if self._on_progress:
            self._on_progress(self._scanned_folders, self._scanned_files)

    def _is_cancelled(self) -> bool:
        if self._cancellation is not None and self._cancellation.is_cancelled:
            self._cancelled = True
            return True
        return False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def scanned_folders(self) -> int:
        return self._scanned_folders

    @property
    def scanned_files(self) -> int:
        return self._scanned_files

    @property
    def inaccessible_count(self) -> int:
        return self._inaccessible

    @property
    def records_retained(self) -> int:
        return self._store.total_retained()

    def records_for(self, folder_path: str) -> Tuple[FileEntry, ...]:
        """Retained records for a folder; re-analyzes *that single folder* on
        demand when its records were evicted (drill-down path, roadmap §9)."""
        key = os.path.normpath(folder_path)
        if self._store.was_evicted(key):
            return self._rescan_folder_records(key)
        records = self._store.records_for_folder(key)
        if records:
            return records
        return self._rescan_folder_records(key)

    def retained_records_for(self, folder_path: str) -> Tuple[FileEntry, ...]:
        """Retained records for a folder with NO re-analysis (UI read path).

        Never calls the classifier: evicted folders simply yield no records
        (the caller should combine with :meth:`is_evicted` to show a
        folder-level-only view). This upholds the zero-reclassification rule
        for the Web UI (Phase 7).
        """
        return self._store.records_for_folder(os.path.normpath(folder_path))

    def is_evicted(self, folder_path: str) -> bool:
        """True when a scanned folder's retained records were all trimmed."""
        return self._store.was_evicted(os.path.normpath(folder_path))

    def _rescan_folder_records(self, folder_path: str) -> Tuple[FileEntry, ...]:
        """Single-folder re-scan (direct files only) for evicted drill-down."""
        pending: List[Tuple[os.DirEntry, os.stat_result]] = []
        assessments: "Dict[str, ScanAssessment]" = {}
        try:
            ctx = prepare_scan_folder(folder_path)
            for entry in os.scandir(folder_path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        st = entry.stat(follow_symlinks=False)
                        pending.append((entry, st))
                        try:
                            assessments[entry.path] = classify_scan(
                                entry.path, filename=entry.name, _ctx=ctx,
                            )
                        except Exception:
                            assessments[entry.path] = classify_scan(
                                entry.path, filename=entry.name,
                                not_resolvable=True, _ctx=ctx,
                            )
                except (OSError, PermissionError):
                    continue
        except (PermissionError, OSError):
            return ()
        return tuple(
            select_folder_raw(
                pending, self._retention_config.per_folder_cap,
                assessments=assessments,
            )
        )

    def aggregation_for(self, folder_path: str) -> FolderAggregation:
        return self.scan_result().per_folder.get(os.path.normpath(folder_path))

    def scan_result(self) -> ScanResult:
        """Fold all per-folder aggregations into a ScanResult.

        ``files_analyzed`` is computed from the FolderInfo tree (accessible
        files only) and is independent of retention: eviction never changes it.
        ``total_descendant_size`` is the root subtree size (root totals already
        include descendants, so it is read from the tree, not summed).

        Each folder's aggregation carries its classification counters and,
        from Phase 5, its ``FolderComposition`` (direct analyzed bytes) and the
        derived folder ``Assessment`` (roadmap §11 short-circuit rules).
        """
        tree = self._scan_tree
        if tree is None:
            return ScanResult(root_path="")
        per_folder: dict = {}
        analyzed = 0
        errors: List[str] = []

        def _composition_for(path: str, direct_size: int) -> FolderComposition:
            t = self._tallies.get(path)
            if t is None:
                return FolderComposition(total_bytes=direct_size)
            return FolderComposition(
                total_bytes=direct_size,
                disposable_bytes=t.disposable_bytes,
                user_value_bytes=t.user_value_bytes,
                protected_critical_bytes=t.protected_critical_bytes,
                known_non_disposable_bytes=t.known_non_disposable_bytes,
                unknown_bytes=t.unknown_bytes,
                not_resolvable_count=t.not_resolvable_count,
                by_category=dict(t.by_category),
            )

        def walk(info: FolderInfo):
            nonlocal analyzed
            path = os.path.normpath(info.path)
            child_files = sum(c.file_count for c in info.children)
            direct_files = info.file_count - child_files
            analyzed += direct_files
            if info.error:
                errors.append(f"{info.path}: {info.error}")
            tally = self._tallies.get(path, _FolderTally())
            composition = _composition_for(path, info.direct_size)
            per_folder[path] = FolderAggregation(
                files_analyzed=direct_files,
                records_retained=self._store.count_for_folder(path),
                total_descendant_size=info.total_size,
                by_impact=dict(tally.by_impact),
                by_recommendation=dict(tally.by_recommendation),
                by_confidence=dict(tally.by_confidence),
                protected_count=tally.protected_count,
                protected_size=tally.protected_size,
                unknown_count=tally.unknown_count,
                unknown_size=tally.unknown_size,
                user_data_count=tally.user_data_count,
                user_data_size=tally.user_data_size,
                app_ids=dict(tally.app_ids),
                composition=composition,
                assessment=derive_folder_recommendation(None, composition),
            )
            for child in info.children:
                walk(child)

        walk(tree)
        return ScanResult(
            root_path=tree.path,
            files_analyzed=analyzed,
            records_retained=self._store.total_retained(),
            total_descendant_size=tree.total_size,
            inaccessible_count=self._inaccessible,
            folder_errors=tuple(errors),
            per_folder=per_folder,
            cancelled=self._cancelled,
        )


def sort_folders_by_size(info: FolderInfo, top_n: int = 20) -> list[FolderInfo]:
    """Return descendants of *info* sorted by size.

    The node passed in (e.g. the scanned root) is never included so that the
    scan root is not exposed as a normal, deletable child folder.
    """
    all_folders = []
    for child in info.children:
        _collect_folders(child, all_folders)
    all_folders.sort(key=lambda f: f.total_size, reverse=True)
    return all_folders[:top_n]


def _collect_folders(info: FolderInfo, result: list[FolderInfo]):
    if info.total_size > 0:
        result.append(info)
    for child in info.children:
        _collect_folders(child, result)