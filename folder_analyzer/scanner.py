"""Multi-threaded disk scanner for Folder Analyzer.

Phase 3: per-file metadata collection (content-analysis Level 1, metadata only).
File ``FileEntry`` records are built reusing the *single* existing
``entry.stat(follow_symlinks=False)`` call per file; no additional syscalls are
issued (timestamps and attributes come from that same stat result; the symlink
flag comes from the DirEntry scandir cache). No classification, no KB lookup, no
assessment: records stay ``category="unknown"`` / ``assessment=None`` until
Phases 4/5.

Retention follows docs/ROADMAP.md §9: bounded, prioritized (non-safe ->
representative -> largest -> path tie-break) with configurable global and
per-folder caps. ``files_analyzed`` always equals 100% of the accessible files;
eviction only reduces ``records_retained``. Folders whose records were evicted
are re-analyzed on demand (single-folder re-scan) for drill-down.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .engine.models import FileEntry, FolderAggregation, ScanResult
from .engine.retention import (
    RetainedFileStore,
    RetentionConfig,
    select_folder_records,
)

ProgressCallback = Callable[[int, int], None]


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


def _build_file_entry(entry: os.DirEntry, st) -> FileEntry:
    """Build a metadata record from an os.scandir DirEntry + its stat result.

    Zero additional syscalls: everything comes from ``entry`` (DirEntry scandir
    cache: name, path, is_file/is_symlink flags) and from the ``st`` stat-result
    the caller already fetched for the size (size, timestamps, mode/ino/nlink).
    """
    name = entry.name
    _, extension = os.path.splitext(name)
    return FileEntry(
        path=entry.path,
        filename=name,
        extension=extension.lower(),
        size=st.st_size,
        created_ts=st.st_ctime,
        modified_ts=st.st_mtime,
        accessed_ts=st.st_atime,
        attributes={
            "st_mode": st.st_mode,
            "st_ino": st.st_ino,
            "st_nlink": st.st_nlink,
            "is_symlink": entry.is_symlink(),
        },
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

    def scan(
        self,
        root_path: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> FolderInfo:
        self._scanned_folders = 0
        self._scanned_files = 0
        self._inaccessible = 0
        self._on_progress = on_progress

        root_path = os.path.normpath(root_path)
        root_info = FolderInfo(
            path=root_path,
            name=os.path.basename(root_path) or root_path,
        )
        self._scan_tree = root_info

        self._scan_folder(root_info, root_path, use_threads=True)
        return root_info

    def _scan_folder(self, info: FolderInfo, path: str, use_threads: bool = True):
        try:
            entries = list(os.scandir(path))
        except (PermissionError, OSError) as e:
            info.error = str(e)
            with self._lock:
                self._scanned_folders += 1
                self._report_progress()
            return

        subdirs: List[os.DirEntry] = []
        file_records: List[FileEntry] = []
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except (OSError, PermissionError):
                        with self._lock:
                            self._inaccessible += 1
                        continue
                    file_records.append(_build_file_entry(entry, st))
                    info.direct_size += st.st_size
                    info.file_count += 1
                    with self._lock:
                        self._scanned_files += 1
                elif entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry)
            except (PermissionError, OSError):
                continue

        with self._lock:
            self._store.record_folder(os.path.normpath(path), file_records)

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

    def is_evicted(self, folder_path: str) -> bool:
        """True when a scanned folder's retained records were all trimmed."""
        return self._store.was_evicted(os.path.normpath(folder_path))

    def _rescan_folder_records(self, folder_path: str) -> Tuple[FileEntry, ...]:
        """Single-folder re-scan (direct files only) for evicted drill-down."""
        records: List[FileEntry] = []
        try:
            for entry in os.scandir(folder_path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        records.append(
                            _build_file_entry(entry, entry.stat(follow_symlinks=False))
                        )
                except (OSError, PermissionError):
                    continue
        except (PermissionError, OSError):
            return ()
        return tuple(select_folder_records(records, self._retention_config.per_folder_cap))

    def aggregation_for(self, folder_path: str) -> FolderAggregation:
        return self.scan_result().per_folder.get(os.path.normpath(folder_path))

    def scan_result(self) -> ScanResult:
        """Fold all per-folder aggregations into a ScanResult.

        ``files_analyzed`` is computed from the FolderInfo tree (accessible
        files only) and is independent of retention: eviction never changes it.
        ``total_descendant_size`` is the root subtree size (root totals already
        include descendants, so it is read from the tree, not summed).
        """
        tree = self._scan_tree
        if tree is None:
            return ScanResult(root_path="")
        per_folder: dict = {}
        analyzed = 0
        errors: List[str] = []

        def walk(info: FolderInfo):
            nonlocal analyzed
            path = os.path.normpath(info.path)
            child_files = sum(c.file_count for c in info.children)
            direct_files = info.file_count - child_files
            analyzed += direct_files
            if info.error:
                errors.append(f"{info.path}: {info.error}")
            per_folder[path] = FolderAggregation(
                files_analyzed=direct_files,
                records_retained=self._store.count_for_folder(path),
                total_descendant_size=info.total_size,
                unknown_count=direct_files,
                unknown_size=info.direct_size,
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