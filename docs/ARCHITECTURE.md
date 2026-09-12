# Folder Analyzer — Architecture

Status: **Phase 3 — file analysis (Level 1) + bounded retention implemented.**
This document intentionally contains only the core/interface boundary, the current
module map, the CLI/Web/Desktop relationship, and the benchmark table. Performance
(§ Phase 8), desktop (§ Phase 9/10), packaging (§ Phase 11), and localization (§ Phase 7)
sections will be expanded in their respective phases.

---

## 1. Core / interface boundary

```
                    FOLDER ANALYZER CORE
                            |
             +--------------+--------------+
             |              |              |
            CLI            WEB          DESKTOP
             |              |              |
           Rich          FastAPI        PySide6
```

**Hard boundary:** `folder_analyzer/` (the core package) MUST NOT import or depend on
FastAPI, Rich, PySide6, or any browser UI. The core owns: scanner, file analysis,
knowledge base, safety model, recommendation engine, folder composition, deletion guard,
and export/domain functionality.

Interfaces:
- **CLI** (`folder_analyzer.__main__`) uses Rich for presentation and calls the core.
- **Web** (`api/`) is a FastAPI adapter over the core; retained as an **optional**
  interface (decision D3).
- **Desktop** (PySide6, Phase 9+) consumes the core **directly in-process**. There is
  **no** `Desktop → localhost FastAPI → Core` path.

## 2. Current module map (Phase 3)

| Module | Responsibility | Boundary |
|---|---|---|
| `folder_analyzer/scanner.py` | Multi-threaded disk scan → `FolderInfo` tree + `ScanResult`; per-file Level-1 metadata (zero extra syscalls); per-folder `FolderAggregation`; on-demand single-folder re-scan (`records_for`) | Core |
| `folder_analyzer/deleter.py` | User-facing safe deletion flow (CLI-level) | Core (UI-agnostic; uses Rich only for CLI presentation) |
| `folder_analyzer/security_guard.py` | Six-condition canonical deletion guard | Core — security boundary |
| `folder_analyzer/audit.py` | Append-only JSON Lines deletion audit log | Core |
| `folder_analyzer/safety.py` | Risk levels + protected path detection (v2 model; superseded for assessment by the three-axis model) | Core |
| `folder_analyzer/engine/enums.py` | Three-axis value spaces: `SystemImpact` / `DeletionRecommendation` / `ConfidenceLevel` | Core — safety model |
| `folder_analyzer/engine/models.py` | Immutable `Assessment` (phase 2, confidence gate I9/I3/I7) + `FileEntry` / `FolderAggregation` / `ScanResult` (phase 3, metadata-only) | Core — safety model + data-model boundary |
| `folder_analyzer/engine/retention.py` | `RetentionConfig` + `RetainedFileStore`: bounded prioritized FileRecord retention (non-safe → representative → largest), lazy `FileEntry` materialization from raw `(DirEntry, stat)` pairs | Core — retention boundary |
| `folder_analyzer/engine/explain.py` | `reason_key` → localized EN/ES text (Phase 2 keys; full i18n migration is Phase 7) | Core |
| `folder_analyzer/utils.py` | Size formatting, drive default | Core |
| `folder_analyzer/treemap.py` | Treemap layout (presentation helper) | Core |
| `folder_analyzer/reporter.py` | Rich reporting helpers | Core |
| `folder_analyzer/exporter.py` | JSON/CSV/HTML export (v1 schema; Phase 6 → v2) | Core |
| `folder_analyzer/i18n.py` | EN/ES string dict (Phase 7 → locales JSON) | Core |
| `api/` | FastAPI app + Pydantic models — web adapter | Interface |
| `web/` | Static front-end (index.html, js, css) | Interface |
| `benchmarks/` | Fixture generator + smoke benchmark (fixed baseline) | Tooling |
| `tests/` | pytest suites | Tooling |

Phase 3 wires the metadata + retention layer: the scanner records every accessible
file (analyzable) but materializes `FileEntry` objects **only for the bounded,
prioritized retained subset**. No classification exists yet (`category="unknown"`,
`assessment=None`); the `by_*` aggregation dicts are structural until Phase 5 populates
them. The classification/recommendation engine integrates in Phase 5.

## 3. CLI / Web / Desktop relationship

- All three interfaces expose the **same** core features (scan, analyze, export, gated
  delete); only presentation differs.
- Deletion is gated by the **same** `security_guard` in CLI and API (and later Desktop),
  so no interface can bypass the deletion boundary.

## 4. Scanner flow (current)

```
Input path ─► Scanner.scan(path) ─► FolderInfo tree  (+ ScanResult via scan_result())
                │
                ├─ per-file (Level 1, metadata only, ZERO extra syscalls):
                │     reuse the single entry.stat(follow_symlinks=False) call
                │     → FileEntry(path, filename, extension, size,
                │                 created/modified/accessed, attributes)
                ├─ record lifecycle DISCOVERED → ANALYZED → RETAINED:
                │     ANALYZED  == 100% of accessible files  (files_analyzed)
                │     RETAINED  == bounded prioritized subset (retention store)
                ├─ per-dir: children, total_size, error
                ├─ retention (roadmap §9): configurable global budget (default
                │     10,000) and per-folder cap (default 200); eviction order
                │     non-safe > representative > largest > path tie-break
                └─ aggregates: FolderAggregation per folder + ScanResult
```

### File-analysis model (Phase 3 as implemented)

- **Three-stage model (roadmap §8):** DISCOVERED (encountered) → ANALYZED (metadata
  extracted) → RETAINED (kept in the bounded store). ANALYZED always equals **100% of
  the accessible files**; eviction only reduces the RETAINED count. The UI must never
  imply "not retained = not analyzed".
- **Level 1 (metadata/path, no file I/O beyond scandir+stat) is implemented** by the
  scanner. It makes **zero additional syscalls**: timestamps and attributes come from
  the same `entry.stat(follow_symlinks=False)` call already needed for the size, and
  the symlink flag comes from the DirEntry scandir cache (verified by an instrumented
  count test: one `stat` per file, one `scandir` per folder).
- **Level 2 (magic bytes, ≤512 B) and Level 3 (targeted bounded inspection, ≤4 KB)
  are NOT implemented in Phase 3.** They belong to Phase 4 (Knowledge Base), where
  ambiguous-type resolution actually needs them. No code path reads file *contents*.
- **Inaccessible files** (permission/OS errors) are counted separately
  (`inaccessible_count`); they are not part of `files_analyzed`.
- **Retention relevance (non-safe) is a structural placeholder in Phase 3 — NOT
  validated by real data.** `_priority` computes `non_safe` only when
  `entry.assessment is not None`; Phase 3 attaches no assessments
  (`FileEntry.assessment is None` for *every* record), so the `non_safe`
  component evaluates to `0` for **all** FileEntry instances — it cannot
  discriminate anything and adds no signal today. The eviction order, when
  assessments exist, is implemented and unit-tested with synthetic Assessments
  (see `test_non_safe_records_survive_eviction_over_largest`); it becomes live
  automatically when the Phase 5 engine attaches real Assessment objects. This
  placeholder must not be read as "validated" — it has no discriminating input
  until Phase 5.
- **On-demand re-analysis:** drilling into a folder whose records were evicted triggers
  a single-folder re-scan (`Scanner.records_for`) that re-reads that folder from disk.

Phase 5 adds per-item and per-folder Safety assessments (emitting the Phase 2 `engine/`
value layer) and populates the `by_impact` / `by_recommendation` / `by_confidence` /
`app_ids` aggregation fields.

## 5. Deletion flow (Phase 1)

```
DeleteRequest ─► security_guard.validate_delete_target(path, scan_root, protected)
                   │
                   ├─ invalid_input  ─► reject (400 / CLI error)
                   ├─ not_found      ─► failure result (no deletion)
                   ├─ not_resolvable ─► deferred (denied; never guessed)
                   ├─ denied_*       ─► blocked (root/ancestor/containment/protected/critical)
                   └─ ok             ─► re-validate ─► send2trash ─► audit record
```

Every attempt writes an audit record (including denied).

## 6. Benchmark baseline (Phase 1 smoke)

Method and reference numbers are recorded in `benchmarks/README.md` and `benchmarks/`.
The **baseline** is established with the deterministic 50k-file fixture and re-run at the
end of every phase. Per-phase results are logged here (append-only table).

| Phase | SCAN TIME (s) | FILES/S | PEAK MEMORY (MB) | RETAINED RECORDS | NOTES |
|---|---|---|---|---|---|
| 1 | **0.816** | **61,290** | **53.65** (RSS delta; Python alloc peak 19.44) | n/a (Phase 3) | **original baseline** — 50,000 files, 37 dirs, 45,451,138,200 B fixture |
| 2 | 0.919 | 54,386 | 50.54 (RSS delta; alloc peak 19.32) | 0 | **Phase-3 reference baseline** (post-security-fix close; engine value layer, scan path untouched) |
| 3 | 1.054 | 47,437 | 59.75 (RSS delta; alloc peak 21.85) | 7,400 | Level-1 metadata + bounded retention (default caps 10,000/200); +14.7% time vs Phase 2 — regression investigation: an initial all-FileEntry materialization measured **2.109 s / 105 MB**, fixed by lazy retention-only materialization (1.046/1.054 s across two runs) |
| … | | | | | |

> **RSS trend watch (Phase 3 close):** peak RSS *decreased* −0.1% at the end of
> Phase 2 versus its own phase reference, but *increased* **+18.2%** in Phase 3
> versus the Phase-2 reference (59.75 vs 50.54 MiB) — close to the 20% gate. This
> trend must be watched closely in **Phase 4** (the Knowledge Base adds more
> in-memory structures — signature registers, type metadata) and formally
> addressed in **Phase 8 (Performance & Scale)** if it keeps climbing. The
> available headroom is ~1.8 percentage points before the gate.

Regression policy: a `>20%` regression vs the documented baseline is a **phase-closing
gate** (stop → investigate → fix/justify → re-run; do not close until resolved or
explicitly user-overridden and documented). See `docs/ROADMAP.md §15/§22`.

## 7. Reference environment

- **OS:** Windows 11 Pro 24H2 (build 26200), 64-bit (`Windows-11-10.0.26200-SP0`)
- **Python:** 3.12.10
- **Hardware:** developer laptop (see machine specs at Phase 1 close)
- **Fixture:** `benchmarks/generated/fixture` — 50,000 files, 37 dirs,
  45,451,138,200 B nominal size, seed `20260101` (sparse files; see `gen_fixture.py`).
- **JSON artifacts:** `benchmarks/results/smoke-phase1.json` (baseline),
  `smoke-phase2-rerun.json` (Phase-2 reference), `smoke-phase3-rerun2.json` (Phase 3).

Any change of environment that legitimately shifts the baseline must be documented with
justification — a new baseline is never established silently.