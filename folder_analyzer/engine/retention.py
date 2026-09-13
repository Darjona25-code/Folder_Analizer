"""Bounded, prioritized FileRecord retention (Phase 3, roadmap §9).

No architectural "200 files per folder"; the store enforces:

- a configurable **global memory budget** (default 10_000 records across all
  folders),
- a configurable **per-folder cap** (default 200 records),
- eviction/relevance priority across the global budget:
    1. non-SAFE_TO_DELETE records first (highest priority to retain),
    2. representative records (one per (folder, category) — the sampler),
    3. largest files,
    4. deterministic tie-break by path.

In Phase 3 nothing is classified yet, so priority 1 is inert (no Assessment is
ever produced) and the effective order is representatives -> largest. Priority 1
is implemented and unit-tested with synthetic Assessments so it becomes live
automatically when the Phase 5 engine starts attaching them. This limitation is
intentional and documented in docs/SAFETY.md and docs/ARCHITECTURE.md.

The ANALYZED count is owned by the scanner, not by this store: eviction here
reduces only ``records_retained``, never ``files_analyzed``.
"""

from __future__ import annotations

import heapq
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .enums import DeletionRecommendation
from .models import AnalysisState, Assessment, FileEntry


@dataclass(frozen=True)
class RetentionConfig:
    """Retention limits — configurable, not hardcoded constants."""

    global_budget: int = 10_000
    per_folder_cap: int = 200


def build_file_entry(
    entry: os.DirEntry,
    st: os.stat_result,
    *,
    is_representative: bool = False,
    analysis_state: AnalysisState = AnalysisState.ANALYZED,
    assessment=None,
    category: str = "unknown",
) -> FileEntry:
    """Build a metadata record from a DirEntry + its already-fetched stat.

    Zero additional syscalls: everything comes from the DirEntry scandir cache
    (name, path, is_symlink) and from ``st`` — the same stat-result the caller
    fetched for the file size. ``assessment`` and ``category`` come from the
    Phase 5 classification layer and are attached when the caller supplies them
    (retained-subset materialization); nothing here performs classification.
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
        is_representative=is_representative,
        analysis_state=analysis_state,
        assessment=assessment,
        category=category,
    )


def select_folder_raw(
    raw_items: Iterable[Tuple[os.DirEntry, os.stat_result]],
    per_folder_cap: int,
    *,
    assessments: Optional[Mapping[str, Assessment]] = None,
) -> List[FileEntry]:
    """Pick the FileEntry records a single folder may contribute.

    Materializes full FileEntry objects ONLY for the kept subset (the rest stay
    analyzed-count-only, never allocated) — this keeps 50k-file scans cheap.
    Selection mirrors ``select_folder_records``: one representative per category
    plus the largest files, capped by ``per_folder_cap``. Returned records are
    RETAINED.

    ``assessments`` maps path -> Assessment (Phase 5 classification). When
    provided, categories come from the classification and kept records carry
    their Assessment (activating the non-SAFE retention priority); without it
    the Phase-3 behavior is preserved (single "unknown" representative, no
    assessment). No classification is performed inside retention.
    """
    if per_folder_cap <= 0:
        return []
    items = list(raw_items)
    if not items:
        return []

    if assessments is None:
        representative = items[0]
        representative_idx = 0
        remaining = per_folder_cap - 1
        if remaining > 0:
            rest = sorted(
                items[1:],
                key=lambda it: (-it[1].st_size, it[0].path),
            )[:remaining]
        else:
            rest = []
        picked: List[Tuple[os.DirEntry, os.stat_result, bool]] = [
            (representative[0], representative[1], True)
        ]
        picked.extend((entry, st, False) for entry, st in rest)
        return [
            build_file_entry(entry, st, is_representative=rep,
                             analysis_state=AnalysisState.RETAINED)
            for entry, st, rep in picked
        ]

    # Phase 5: one representative per category (its first item in encounter
    # order), then the largest remaining files up to the cap.
    representatives: List[Tuple[os.DirEntry, os.stat_result]] = []
    seen_categories: Set[str] = set()
    for entry, st in items:
        category = getattr(assessments.get(entry.path), "detected_category", None) \
            or "unknown"
        if category not in seen_categories:
            seen_categories.add(category)
            representatives.append((entry, st))
    remaining = per_folder_cap - len(representatives)
    rest = []
    if remaining > 0:
        rest_items = sorted(
            items,
            key=lambda it: (-it[1].st_size, it[0].path),
        )
        rep_paths = {e.path for e, _ in representatives}
        rest = [
            (e, st) for e, st in rest_items
            if e.path not in rep_paths
        ][:remaining]
    returned = []

    def _category_for(entry) -> str:
        assessment = assessments.get(entry.path)
        if assessment is not None and assessment.detected_category:
            return assessment.detected_category
        return "unknown"

    for entry, st in representatives:
        returned.append(build_file_entry(
            entry, st, is_representative=True,
            analysis_state=AnalysisState.RETAINED,
            assessment=assessments.get(entry.path),
            category=_category_for(entry),
        ))
    for entry, st in rest:
        returned.append(build_file_entry(
            entry, st, is_representative=False,
            analysis_state=AnalysisState.RETAINED,
            assessment=assessments.get(entry.path),
            category=_category_for(entry),
        ))
    return returned


def _priority(entry: FileEntry) -> Tuple[int, int, int, str]:
    """Heap priority key; heapq pops the *smallest*, i.e. evicts lowest priority.

    Larger tuple = more important = survives global eviction:
      1. non-SAFE_TO_DELETE records (real relevance signal, Phase 5);
      2. representative records (sampler);
      3. size ascending (so large files dominate);
      4. path as the deterministic tie-break.
    """
    non_safe = (
        1
        if entry.assessment is not None
        and entry.assessment.recommendation is not DeletionRecommendation.SAFE_TO_DELETE
        else 0
    )
    representative = 1 if entry.is_representative else 0
    return (non_safe, representative, entry.size, entry.path)


def select_folder_records(
    entries: Iterable[FileEntry],
    per_folder_cap: int,
) -> List[FileEntry]:
    """Pick the records a single folder may contribute.

    Keeps up to ``per_folder_cap`` records: one representative per category
    (first record of each category in encounter order, marked
    ``is_representative=True``) plus the largest files, so a category is never
    entirely absent from the store even when its files are small.

    Phase 3 has exactly one category ("unknown"), so each folder contributes at
    most one representative.
    """
    if per_folder_cap <= 0:
        return []
    entries = list(entries)
    representatives: List[FileEntry] = []
    seen_categories: Set[str] = set()
    for entry in entries:
        if entry.category not in seen_categories:
            seen_categories.add(entry.category)
            representatives.append(
                FileEntry(
                    path=entry.path,
                    filename=entry.filename,
                    extension=entry.extension,
                    size=entry.size,
                    created_ts=entry.created_ts,
                    modified_ts=entry.modified_ts,
                    accessed_ts=entry.accessed_ts,
                    attributes=entry.attributes,
                    assessment=entry.assessment,
                    category=entry.category,
                    is_representative=True,
                    analysis_state=entry.analysis_state,
                )
            )
    remaining = per_folder_cap - len(representatives)
    if remaining > 0:
        largest = heapq.nlargest(remaining, entries, key=lambda e: (e.size, e.path))
        largest_set = {id(e) for e in largest}
    else:
        largest = []
        largest_set = set()
    merged: Dict[str, FileEntry] = {r.path: r for r in representatives}
    for entry in largest:
        if id(entry) not in largest_set or entry.path in merged:
            continue
        merged[entry.path] = entry
    return [
        FileEntry(
            path=e.path,
            filename=e.filename,
            extension=e.extension,
            size=e.size,
            created_ts=e.created_ts,
            modified_ts=e.modified_ts,
            accessed_ts=e.accessed_ts,
            attributes=e.attributes,
            assessment=e.assessment,
            category=e.category,
            is_representative=e.is_representative,
            analysis_state=AnalysisState.RETAINED,
        )
        for e in merged.values()
    ]


class RetainedFileStore:
    """Priority-bounded store keeping at most ``config.global_budget`` records.

    ``record_folder`` trims per-folder records down to ``per_folder_cap`` and
    merges them into a global min-heap, evicting the lowest-priority records
    whenever the global budget is exceeded. Thread-safe: callers (the
    multi-threaded scanner) must hold the scanner lock while calling it.
    """

    def __init__(self, config: RetentionConfig) -> None:
        self.config = config
        self._heap: List[Tuple[int, int, int, str, FileEntry]] = []
        self._living: Dict[str, FileEntry] = {}
        self._folder_paths: Dict[str, Set[str]] = {}
        self._owned_by: Dict[str, str] = {}
        self._folder_had_files: Set[str] = set()

    def record_folder(
        self,
        folder_path: str,
        raw_items: Iterable[Tuple[os.DirEntry, os.stat_result]],
        *,
        assessments: Optional[Mapping[str, Assessment]] = None,
    ) -> int:
        """Register a folder's analyzed records; returns how many were retained.

        Trims the folder down to ``per_folder_cap`` (representatives first,
        else largest), merges into the global budget and evicts lowest-priority
        records when the budget is exceeded. Eviction here affects only the
        retained count, never the ANALYZED count (owned by the scanner).

        ``assessments`` (path -> Assessment, Phase 5 classification) is used
        for per-category representatives and is attached to the retained records
        so the non-SAFE retention priority becomes live; retention never
        classifies.
        """
        selected = select_folder_raw(
            raw_items, self.config.per_folder_cap, assessments=assessments,
        )
        return self._record_selected(folder_path, selected)

    def add_entries(
        self,
        folder_path: str,
        entries: Iterable[FileEntry],
    ) -> int:
        """FileEntry-level entry point (Phase 5 classification feed / tests).

        Applies the same per-folder cap + global priority eviction. The
        scanner's bulk path uses ``record_folder`` with raw DirEntry/stat pairs
        so FileEntry objects are only materialized for the kept subset.
        """
        return self._record_selected(folder_path, select_folder_records(
            entries, self.config.per_folder_cap))

    def _record_selected(self, folder_path: str, selected: List[FileEntry]) -> int:
        if selected:
            self._folder_had_files.add(folder_path)
        folder_paths = self._folder_paths.setdefault(folder_path, set())
        for entry in selected:
            self._living[entry.path] = entry
            self._owned_by[entry.path] = folder_path
            folder_paths.add(entry.path)
            heapq.heappush(self._heap, _priority(entry) + (entry,))
        self._trim()
        return self.count_for_folder(folder_path)

    def _trim(self) -> None:
        while len(self._living) > self.config.global_budget:
            *_, evicted = heapq.heappop(self._heap)
            if evicted.path not in self._living:
                continue
            self._living.pop(evicted.path, None)
            folder = self._owned_by.pop(evicted.path, None)
            if folder is not None:
                self._folder_paths[folder].discard(evicted.path)

    def count_for_folder(self, folder_path: str) -> int:
        return len(self._folder_paths.get(folder_path, set()))

    def records_for_folder(self, folder_path: str) -> Tuple[FileEntry, ...]:
        folder_paths = self._folder_paths.get(folder_path)
        if not folder_paths:
            return ()
        return tuple(
            self._living[p] for p in sorted(folder_paths) if p in self._living
        )

    def was_evicted(self, folder_path: str) -> bool:
        """True when a folder's records were all trimmed by the global budget."""
        return (
            folder_path in self._folder_had_files
            and not self._folder_paths.get(folder_path)
        )

    def total_retained(self) -> int:
        return len(self._living)