"""Multi-threaded disk scanner for Folder Analyzer."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field


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


class Scanner:
    def __init__(self, max_workers: int = 16):
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._scanned_folders = 0
        self._scanned_files = 0
        self._on_progress = None

    def scan(self, root_path: str, on_progress=None) -> FolderInfo:
        self._scanned_folders = 0
        self._scanned_files = 0
        self._on_progress = on_progress

        root_path = os.path.normpath(root_path)
        root_info = FolderInfo(
            path=root_path,
            name=os.path.basename(root_path) or root_path,
        )

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

        subdirs = []
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    try:
                        size = entry.stat(follow_symlinks=False).st_size
                    except (OSError, PermissionError):
                        continue
                    info.direct_size += size
                    info.file_count += 1
                    with self._lock:
                        self._scanned_files += 1
                elif entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry)
            except (PermissionError, OSError):
                continue

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


def sort_folders_by_size(info: FolderInfo, top_n: int = 20) -> list[FolderInfo]:
    all_folders = []
    _collect_folders(info, all_folders)
    all_folders.sort(key=lambda f: f.total_size, reverse=True)
    return all_folders[:top_n]


def _collect_folders(info: FolderInfo, result: list[FolderInfo]):
    if info.total_size > 0:
        result.append(info)
    for child in info.children:
        _collect_folders(child, result)
