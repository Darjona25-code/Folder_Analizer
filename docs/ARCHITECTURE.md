# Folder Analyzer — Architecture

Status: **Phase 2 — scaffold + safety-model foundation.** This document intentionally
contains only the core/interface boundary, the current module map, the CLI/Web/Desktop
relationship, and the benchmark baseline placeholder. File analysis/retention
(§ Phase 3), performance (§ Phase 8), desktop (§ Phase 9/10), packaging (§ Phase 11),
and localization (§ Phase 7) sections will be expanded in their respective phases.

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

## 2. Current module map (Phase 2)

| Module | Responsibility | Boundary |
|---|---|---|
| `folder_analyzer/scanner.py` | Multi-threaded disk scan → `FolderInfo` tree | Core |
| `folder_analyzer/deleter.py` | User-facing safe deletion flow (CLI-level) | Core (UI-agnostic; uses Rich only for CLI presentation) |
| `folder_analyzer/security_guard.py` | Six-condition canonical deletion guard | Core — security boundary |
| `folder_analyzer/audit.py` | Append-only JSON Lines deletion audit log | Core |
| `folder_analyzer/safety.py` | Risk levels + protected path detection (v2 model; superseded for assessment by the three-axis model) | Core |
| `folder_analyzer/engine/enums.py` | Three-axis value spaces: `SystemImpact` / `DeletionRecommendation` / `ConfidenceLevel` | Core — safety model |
| `folder_analyzer/engine/models.py` | Immutable `Assessment` + construction-time confidence gate (I9) with I3/I7 floors | Core — safety model boundary |
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

Phase 2 adds the `folder_analyzer/engine/` safety-model foundation (enums,
`Assessment`, confidence gate, explain). Nothing in the live scan/delete pipeline
consumes it yet — the classifier/recommendation engine integrates in Phase 5.

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
assessments (emitted by the Phase 2 `engine/` value layer).

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
| 1 | **0.816** | **61,290** | **53.65** (RSS delta; Python alloc peak 19.44) | n/a (Phase 3) | **baseline reference** — 50,000 files, 37 dirs, 45,451,138,200 B fixture |
| 2 | | | | | |
| 3 | | | | | |
| … | | | | | |

Regression policy: a `>20%` regression vs the documented baseline is a **phase-closing
gate** (stop → investigate → fix/justify → re-run; do not close until resolved or
explicitly user-overridden and documented). See `docs/ROADMAP.md §15/§22`.

## 7. Reference environment

- **OS:** Windows 11 Pro 24H2 (build 26200), 64-bit (`Windows-11-10.0.26200-SP0`)
- **Python:** 3.12.10
- **Hardware:** developer laptop (see machine specs at Phase 1 close)
- **Fixture:** `benchmarks/generated/fixture` — 50,000 files, 37 dirs,
  45,451,138,200 B nominal size, seed `20260101` (sparse files; see `gen_fixture.py`).
- **JSON artifact:** `benchmarks/results/smoke-phase1.json`

Any change of environment that legitimately shifts the baseline must be documented with
justification — a new baseline is never established silently.