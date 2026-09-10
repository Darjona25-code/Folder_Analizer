# Folder Analyzer — Architecture

Status: **Phase 1 — scaffold only.** This document intentionally contains only the
core/interface boundary, the current module map, the CLI/Web/Desktop relationship, and
the benchmark baseline placeholder. File analysis/retention (§ Phase 3), performance
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

## 2. Current module map (Phase 1)

| Module | Responsibility | Boundary |
|---|---|---|
| `folder_analyzer/scanner.py` | Multi-threaded disk scan → `FolderInfo` tree | Core |
| `folder_analyzer/deleter.py` | User-facing safe deletion flow (CLI-level) | Core (UI-agnostic; uses Rich only for CLI presentation) |
| `folder_analyzer/security_guard.py` | Six-condition canonical deletion guard | Core — security boundary |
| `folder_analyzer/audit.py` | Append-only JSON Lines deletion audit log | Core |
| `folder_analyzer/safety.py` | Risk levels + protected path detection (v2 model; Phase 2 replaces with three-axis model) | Core |
| `folder_analyzer/utils.py` | Size formatting, drive default | Core |
| `folder_analyzer/treemap.py` | Treemap layout (presentation helper) | Core |
| `folder_analyzer/reporter.py` | Rich reporting helpers | Core |
| `folder_analyzer/exporter.py` | JSON/CSV/HTML export (v1 schema; Phase 6 → v2) | Core |
| `folder_analyzer/i18n.py` | EN/ES string dict (Phase 7 → locales JSON) | Core |
| `api/` | FastAPI app + Pydantic models — web adapter | Interface |
| `web/` | Static front-end (index.html, js, css) | Interface |
| `benchmarks/` | Fixture generator + smoke benchmark (fixed baseline) | Tooling |
| `tests/` | pytest suites | Tooling |

## 3. CLI / Web / Desktop relationship

- All three interfaces expose the **same** core features (scan, analyze, export, gated
  delete); only presentation differs.
- Deletion is gated by the **same** `security_guard` in CLI and API (and later Desktop),
  so no interface can bypass the deletion boundary.

## 4. Scanner flow (current)

```
Input path ─► Scanner.scan(path) ─► FolderInfo tree
                │
                ├─ per-file: size (file_count, direct_size)
                ├─ per-dir: children, total_size, error
                └─ aggregates: total_size / file_count / folder_count
```

Phase 3 adds per-file metadata, three-level content analysis, and the
DISCOVERED/ANALYZED/RETAINED states. Phase 5 adds per-item and per-folder Safety
assessments.

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
| 1 | _(recorded at Phase 1 close)_ | | | n/a (Phase 3) | baseline reference |
| 2 | | | | | |
| 3 | | | | | |
| … | | | | | |

Regression policy: a `>20%` regression vs the documented baseline is a **phase-closing
gate** (stop → investigate → fix/justify → re-run; do not close until resolved or
explicitly user-overridden and documented). See `docs/ROADMAP.md §15/§22`.

## 7. Reference environment

Documented at baseline: OS, Python version, hardware (the developer laptop). Any change
of environment that legitimately shifts the baseline must be documented with
justification — a new baseline is never established silently.