# Folder Analyzer - Session Continuation

If you need to continue this development session on another PC, open opencode and share this link:

**Link:** https://opncd.ai/share/a8LeCjC2

> **Handoff completo (2026-09-10, fin de Phase 3):** lee `session/HANDOFF-2026-09-10-ES.md`
> para el estado íntegro y las instrucciones. Para restaurar la conversación completa:
> `opencode import session\session-export-phase3-sanitized.json`
> (export sanitizado con `opencode export <sessionId> --sanitize`).

## Session Summary

- **Date:** September 2026
- **Project:** Folder Analyzer v2.0.0
- **Location:** `C:\OPENCODE\Folder_Analyzer`
- **GitHub:** https://github.com/Darjona25-code/Folder_Analizer

### What was built

A disk space analyzer with two front-ends:

- **Interactive CLI** with Rich tables/trees/progress bars, ASCII treemap, Rise/risk safety system (CRITICAL/CAUTION/SAFE), Recycle Bin deletion, JSON/CSV/HTML export, bilingual (EN/ES).
- **Web UI** with a FastAPI backend (`api/`) + static frontend (`web/`): drive stats, sortable folder table, treemap, exports.

### Recent repairs (12 issues)

Root-folder exclusion and scan-root deletion protection (CLI + API), clean EOF handling in the CLI, correct drill-down indexing, API scan state moved to `app.state` (opt-in reload via `FOLDER_ANALYZER_RELOAD=1`), `Field(default_factory=list)` for models, iterative `get_folder_size` (no recursion crash), `AppData\Roaming` flagged CAUTION, frontend uses detected drive labels and separates scanned vs drive stats, localized exports (CSV/HTML + API `lang`), valid setuptools `build-backend`, version consistency, expanded i18n.

### Tech stack

- Python 3.10+ (tested on 3.12)
- Rich (terminal UI), send2trash (Recycle Bin), psutil (disk info)
- FastAPI + Uvicorn (web), httpx (API testing)
- pytest — 81 tests passing

### To continue development

```bash
cd /d C:\OPENCODE\Folder_Analyzer
python -m folder_analyzer --lang es --path C:\

# Web UI
python -m api
```

### To install the CLI as a command

```bash
python -m venv .venv
.venv\Scripts\activate
pip install .
folder-analyzer --path C:\
```

## Phase 1 — Deletion Security Hardening (COMPLETED)

- **Delivered:** six-condition canonical deletion guard (`security_guard.py`), append-only
  JSONL audit log (`audit.py`), shared guard in API `/api/delete` + CLI delete flow,
  deletion-security test suite, deterministic 50k-file smoke benchmark with baseline
  (0.816 s / 61,290 files/s / 53.65 MiB peak RSS, `docs/ARCHITECTURE.md` §6).
- **Security follow-up (this commit):** protected/critical path checks now evaluate the
  canonical identity (`target_key`) instead of the raw input path, closing a `\\?\`-prefix
  bypass of Tier-0/critical roots under a containing scan root. Tests:
  `test_extended_length_prefix_cannot_bypass_tier0_protection` + positive control.
- **Doc corrections:** SAFETY.md/ROADMAP.md behavior matrix no longer claims scan-time
  `NOT_RESOLVABLE` surfacing is implemented; it is explicitly deferred to Phase 3/5.
  Phase 1 implements delete-time handling only (`DENIED` / `400 UNRESOLVABLE_PATH` /
  CLI message / audit `deferred`).
- **State before Phase 2:** test suite green (110 passed, 2 symlink skips); all Phase 1
  commits pushed to `origin/master`.
- **Next:** Phase 2 — Safety Engine Model (three-axis enums, invariants I1–I3/I9,
  Confidence semantics; no UI behavior change).

## Phase 2 — Safety Engine Model (COMPLETED)

- **Delivered** (`folder_analyzer/engine/`):
  - `enums.py` — `SystemImpact` (NONE/LOW/MODERATE/HIGH/CRITICAL/UNKNOWN),
    `DeletionRecommendation` (SAFE_TO_DELETE/REVIEW_FIRST/KEEP/DO_NOT_DELETE),
    `ConfidenceLevel` (HIGH/MEDIUM/LOW).
  - `models.py` — frozen `Assessment` dataclass (impact, recommendation, confidence,
    reason_key/reason_params, detected_category, app_id, is_user_data, is_temporary).
    Confidence gate (I9) enforced **inside `__post_init__`** (`SAFE_TO_DELETE` without
    `HIGH` confidence → `REVIEW_FIRST`), plus I3 (UNKNOWN impact) and I7 (`is_user_data`)
    floors — the invalid combination is structurally unrepresentable. `apply_confidence_gate`
    exposed as a pure, idempotent function.
  - `explain.py` — `reason_key` → localized EN/ES text (10 keys, `{param}` interpolation,
    unknown keys fall back to the key), mirroring the `i18n.py` pattern.
  - No FileEntry/ScanResult/FolderAggregation and **no pipeline integration** (as scoped).
- **Tests:** `tests/test_safety_invariants.py` (I1, I2, I3-item, I7, I9 exhaustive,
  I10 scaffold + immutability) + `tests/test_explain.py`. Suite grew **110 → 129 passed,
  2 skipped**.
- **Benchmark (scan path unchanged by Phase 2):** 0.92–0.94 s scan, ~53–54k files/s,
  ~50.5–53.0 MiB peak RSS — within run-to-run variance of the Phase 1 baseline (gate: >20%
  regression).
- **Docs:** `docs/SAFETY.md` §6 (three-axis model as implemented + construction-time gate),
  §9 status table I1–I10, §11 re-scoped to Phase 5 composition; `docs/ARCHITECTURE.md`
  module map + flows now list `engine/`.
- **Logs:** commit list includes a `feat(engine)` commit, a `test` commit, and a `docs`
  commit (this one also updates CHANGELOG/SESSION); all pushed to `origin/master`.
- **Next:** Phase 3 — File Analysis Engine (per-file metadata, three-level analysis,
  DISCOVERED/ANALYZED/RETAINED states, scan-time NOT_RESOLVABLE surfacing).

## Phase 3 — File Analysis & Data Model (COMPLETED)

- **Delivered** (approved scope):
  - `engine/models.py` — `AnalysisState` (DISCOVERED/ANALYZED/RETAINED), frozen
    `FileEntry` (path, filename, extension, size, created/modified/accessed,
    attributes, `assessment=None`, `category="unknown"`, `is_representative`,
    `analysis_state`), frozen `FolderAggregation` + `ScanResult`.
  - `engine/retention.py` — `RetentionConfig` (global budget default 10,000,
    per-folder cap default 200), `RetainedFileStore`: lazy raw `(DirEntry, stat)`
    piping, eviction priority non-safe → representative → largest → path,
    `was_evicted`/counters, single-folder re-fetch API.
  - `folder_analyzer/scanner.py` — Level-1 per-file metadata with **zero extra
    syscalls** (one `stat` per file, one `scandir` per dir, verified by an
    instrumented-count test); `records_for`/`is_evicted`/`scan_result`/
    `aggregation_for`; `files_analyzed` ALWAYS = 100% of accessible files.
  - **Level 2 (magic bytes ≤512 B) / Level 3 (≤4 KB) NOT implemented** — moved to
    Phase 4; classification/composition remain Phase 5 (docs updated to state this
    explicitly).
- **Tests:** `tests/test_file_analysis.py` (12 tests). Suite grew **133 → 145 passed,
  2 skipped**.
- **Benchmark (vs Phase 2 reference 0.919 s / 54,386 files/s / 50.54 MiB):** Phase 3 =
  1.054 s / 47,437 files/s / 59.75 MiB (+14.7% time, within 20% gate), 7,400 retained.
  Gate hit during development: naive all-records materialization measured 2.109 s /
  105 MiB → root-caused (FileEntry object churn) and fixed by lazy retention-only
  materialization (`perf(scanner)` commit).
- **Docs:** `docs/ARCHITECTURE.md` (scanner flow + file-analysis model + §6 benchmark
  rows Phases 2/3, incl. the regression investigation); `docs/SAFETY.md` §6.1
  content-analysis levels + limitation #6; `docs/ROADMAP.md` Phase 3 marked complete.
- **Logs:** `feat(engine)` (models+retention), `feat(scanner)` (metadata + benchmark
  wiring), `test` (file-analysis suite), `perf(scanner)` (lazy materialization),
  `docs` (Phase 3). Pushed to `origin/master`.
- **Next:** Phase 4 — Knowledge Base (Levels 2/3 content detection as re-scoped,
  signature registers, optional foundation-data feeds).

## Phase 4 — Knowledge Base (COMPLETED — standalone, not wired)

- **Delivered** (approved scope, location `folder_analyzer/engine/kb/` per approval):
  - T0 `known_paths.py` — critical/system paths; `_EXACT` (drive root, exact-match
    only, bisect over sorted tables) + `_TREE` (SystemRoot/System32/SysWOW64/
    ProgramFiles/ProgramData/`$Recycle.Bin`/System Volume Information/Recovery).
  - T1 `env_paths.py` — env vars + Known Folders (`SHGetKnownFolderPath`, ctypes,
    win32 only), most-specific-first (Downloads/Documents/Desktop before
    USERPROFILE), resolved **once per scan session**.
  - T2 `categories.py` — component patterns in order browser → dev → ai_ml → game →
    docker → cache; T3 curated extension table (~90 entries, material only);
    T3 evaluated before Tiers 4–5 (extension evidence short-circuits T4).
  - T4 `apps.py` — `app:ollama` / `app:docker` / `app:python` / `app:node` /
    `app:browser` (anchors deliberately absent from T2 so dispatch reaches T4).
  - T5 `registry.py` — Uninstall catalog, batch-loaded once/session, safe-empty;
    `content.py` — Level 2 (≤512 B) magic + Level 3 (≤4 KB) SQLite windowed /
    Ollama-manifest (path must contain `ollama`+`manifests`); no full-file read path.
  - `kb/__init__.py` dispatcher: tiers 0→5, first non-None wins, else
    `unknown`/`tier=None`/`low`. `KBResult` carries category/tier/confidence_hint/
    level/detail; **never constructs Assessment**; `kb.reset_session_caches()`.
- **Test-driven fixes surfaced by the 31 new tests:** registry `_catalog()` hardened
  to safe-empty even when `_batch_load` raises; Tier-2 order changed so browser
  evidence precedes generic cache (`Chrome\Cache` → browser).
- **Tests:** `tests/test_knowledge_base.py` (31 tests). Suite grew **148 → 179 passed,
  2 skipped**.
- **Benchmark (scan path byte-identical to Phase 3 — no KB import in scanner; analysis/
  composition time still 0.0):** six runs `1.001–1.495 s`, files/s `33,455–49,973`,
  RSS `58.8–78.3` MiB. Spread is machine noise (±25%); best run 1.001 s is at/under the
  Phase-3 baseline. Artifacts `benchmarks/results/smoke-phase4-r1..6.json`; row in
  `docs/ARCHITECTURE.md` §6.
- **Docs:** `docs/ARCHITECTURE.md` (status + module map + KB model + memory footprint
  ~tens of KB / <100 KB + RSS trend status + Phase-4 benchmark), `docs/SAFETY.md`
  (categories-not-Assessments confirmation; L2/L3 implemented but standalone),
  `docs/ROADMAP.md` Phase 4 → COMPLETE, `CHANGELOG.md` [Unreleased].
- **Logs:** `feat(kb)` (`f41d85c`), `test(kb)` (`9253a5b`), `docs` (Phase 4). Pushed to
  `origin/master`.
- **Next:** Phase 5 — Recommendation Engine + Folder Composition + ScanResult (wire the
  KB into per-item/per-folder Assessment; I1–I3/I9 positive evidence; composition
  short-circuits R1–R6). Watch RSS headroom (~1.8pp to the 20% gate).

## Phase 5 — Recommendation Engine + Folder Composition + ScanResult (COMPLETED)

- **Delivered** (approved scope, commits `ee44266` / `1a85a8c` / `96cdb16`):
  - `engine/classifier.py` — `classify_path`/`classify_scan`: KB result → policy →
    `Assessment` / lean frozen `ScanAssessment` (bucket precomputed). Successful
    pipeline only; `NOT_RESOLVABLE` returns `None` and aggregator normalizes to
    `UNKNOWN`/`unknown`. `assessment_from_scan_record` materializes a full
    `Assessment` from a record (parity-tested).
  - `engine/recommender.py` — `CompositionBucket` (starts 100% UNKNOWN, split by
    real classification) + `derive_folder_recommendation`: roadmap §11 short-circuit
    R1–R5, named `CompositionConfig` (0.85 / 0.10 / 0.15 / unknown-block 0.0),
    R3 demotion (`unknown ≥ 0.25`), Downloads policy floor (REVIEW_FIRST), oversize
    100 GB case, empty-tree handling. Shares always sum to 100% of descendant bytes.
  - Scan wiring — `scanner.py` calls `classify_scan` per file and tags every record;
    `retention.py` materializes full Assessments only for the retained subset;
    `scanner._bump` reads precomputed scan-record fields; `ScanResult`/
    `FileEntry`/`FolderAggregation` expose live assessments + folder composition.
  - I10 authority (integration test `tests/test_i10_integration.py`): a guard-valid
    `SAFE_TO_DELETE`+`HIGH` item beneath a folder-derived `REVIEW_FIRST` remains
    deletable; folder review gates only the folder-as-a-whole action.
  - Perf discipline (`96cdb16`): scan path normalizes each path **once** (tier
    `classify` accepts precomputed `_key`); lazy `_TIER_MODULES` dict; Tier-2 marker
    union fast-path; `slots=True` on `Assessment`/`ScanAssessment`; item-level
    `reason_params` dropped (static reason keys; category lives in
    `detected_category`).
  - Tests: `tests/conftest.py` `classification_neutral_env` + `scan_sandbox`
    fixtures (scan tests immune to the real `%TEMP%`); 8 canonical examples;
    NOT_RESOLVABLE→UNKNOWN; scan-record ⇄ Assessment parity;
    scanner end-to-end metadata/aggregation/retention with real classification.
- **Suite:** **304 passed, 2 skipped.**
- **Benchmark (Phase 5 harness, pinned):** 3 runs 4.717–4.823 s; gate alloc-peak
  **13.14–14.04 MiB** (+4.3…+14.3% vs corrected 4′ upper bound; +15.5…+20.6% vs
  lower bound), retained_records **7,400 @ +0%** — within the 20% phase-closing gate.
  Wall time is inflated by tracemalloc tracking ~10M per-file classification
  allocations; uninstrumented classification cost ≈ 0.7 s (+70%). RSS envelope
  36.41–38.28 MiB (informational). Rows + artifacts in `docs/ARCHITECTURE.md` §6
  (`phase5-pinned-r1..r3.json`, latest `phase5-pinned.json`); note
  `benchmarks/results/` is gitignored (local reference only).
- **Docs:** `docs/ARCHITECTURE.md` (module map → Phase 5, KB wiring §2, phase-5
  baseline row §6), `docs/SAFETY.md` (I3/I10 → implemented, retention activation,
  §10/§11), `docs/ROADMAP.md` (Phase 5 → COMPLETE, status header), `CHANGELOG.md`.
- **Next:** Phase 6 — Exports v2 (export schema v2 with assessment fields +
  `analysis_state` markers; deterministic CSV/HTML/JSON).