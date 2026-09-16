# Folder Analyzer - Session Continuation

If you need to continue this development session on another PC, open opencode and share this link:

**Link:** https://opncd.ai/share/a8LeCjC2

> **Handoff completo (2026-09-10, fin de Phase 3):** lee `session/HANDOFF-2026-09-10-ES.md`
> para el estado íntegro y las instrucciones. Para restaurar la conversación completa:
> `opencode import session\session-export-phase3-sanitized.json`
> (export sanitizado con `opencode export <sessionId> --sanitize`).

## Session Summary

- **Date:** September 2026
- **Project:** Folder Analyzer v3.0.0
- **Location:** `C:\OPENCODE\Folder_Analyzer`
- **GitHub:** https://github.com/Darjona25-code/Folder_Analizer

### What was built

A disk space analyzer with two front-ends:

- **Interactive CLI** with Rich tables/trees/progress bars, ASCII treemap, Rise/risk safety system (CRITICAL/CAUTION/SAFE), Recycle Bin deletion, JSON/CSV/HTML export, bilingual (EN/ES).
- **Web UI** with a FastAPI backend (`api/`) + static frontend (`web/`): drive stats, sortable folder table, treemap, exports.
- **Desktop UI** (Phase 9 → Phase 10) — native PySide6 app consuming the core in-process: scan table, drill-down per-folder file view, read-only reasons panel, JSON/CSV/HTML export (core exporter v2), language settings persisted under the user profile, identical safety/delete/I10 gates.

### Phase 10 — Desktop Application Complete (CLOSED / APPROVED 2026-09-16)

- **Drill-down file view (D1–D5):** `QStackedWidget` top/drill pages; file rows
  sourced ONLY from `Scanner.retained_records_for` (zero re-classification);
  evicted folders → empty rows + folder-level-only notice (D3). I10 gate per file
  row (`a.tmp`/`b.tmp` actionable under a REVIEW_FIRST parent; `notes.txt` not).
- **Read-only reasons panel (R1–R4):** `details_dialog.py` — name/size/rec/conf/
  imp/reason from the same localized row fields; no delete control present.
- **Export (E1–E4):** `export_dialog.py`, delegates to `export_json_v2`/
  `export_csv_v2`/`export_html_v2`; zero export logic in `desktop_app/`. Desktop
  path re-measured on the 50k fixture: JSON 2.16 / CSV 0.63 / HTML 0.75 ms medians
  (Phase-6 baseline 2.6 / 0.9 / 0.8 ms). Cancellation: no new mechanism (per the
  approved clarification); timing re-measurement is the required evidence.
- **Settings (S1–S2):** language-only; `AppSettings` persists to
  `%APPDATA%/FolderAnalyzer/folder-analyzer-desktop.json`; live re-localization;
  applied on next launch; invalid lang → `en`.
- **i18n (I1–I3):** 9 new keys per locale (`col_name`, `desktop_back`,
  `desktop_details`, `desktop_no_files`, `desktop_open`, `desktop_settings`,
  `settings_language`, `btn_save`, `btn_browse`), EN/ES parity enforced.
- **Delete matrix (DM1):** folder rows and drill-down file rows share
  `controller._guarded_delete` (`validate_delete_target` → confirm → `revalidate`
  → `send2trash`); verified by tests (missing/outside/scan-root blocked).
- **Engine frozen:** `git diff --stat c2320ad..HEAD` over `folder_analyzer/engine`,
  scanner.py, safety.py, security_guard.py, deleter.py is EMPTY.
- **Suite:** 384 → **397 passed / 2 skipped** (+13 desktop tests). Commits
  `232f704` → `bb75b7a` (5 Conventional Commits). Docs close: README desktop
  section + screenshots, CHANGELOG, ARCHITECTURE, ROADMAP.
- **Closure:** Phase 10 evidence accepted in full by the user (2026-09-16)
  after the 4-item residual round: benchmark JSON committed and tracked
  (`cb9afd3`, gitignored path lifted via `git add -f`), real screenshot byte
  sizes proven from committed blobs, evidence scripts declared disposable
  one-off artifacts, integrity commitment given in writing. Phase 9 status:
  superseded by the approved Phase 10.

### Phase 11 — Packaging & Installer (DELIVERED 2026-09-16, awaiting acceptance)

- **PyInstaller onedir bundle of the desktop app only** (R1: CLI packaging and
  the wheel/entry-point mechanism untouched). `packaging/FolderAnalyzer.spec`:
  `console=False`, locales added as data at `folder_analyzer/locales` (the
  exact dir the frozen `i18n.load_locales()` looks up relative to `__file__`),
  core consumed in-process (ADR-001). Output `dist/FolderAnalyzer/`: exe
  2,442,001 B, tree 116,718,796 B / 172 files.
- **Installer MANDATORY (R2, R3):** Inno Setup 6.7.3 (per-user at
  `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`) — `packaging/
  folder-analyzer.iss` → `dist/FolderAnalyzer-Setup-3.0.0.exe`. Silent
  install into a fresh dir (exit 0; installed tree 121,218,225 B; locales
  present), installed-output `--selftest` exit 0 passed=true with Python off
  the PATH, silent uninstall exit 0 (dir removed).
- **Version 3.0.0 (R6):** `pyproject.toml`, `folder_analyzer/__init__.py`,
  `api/main.py`. DELIBERATE ahead-of-tag: string 3.0.0 with NO `v3.0.0` tag
  until Phase 12 (ROADMAP §18). Locale `package-data` declared so the wheel
  carries `folder_analyzer/locales/{en,es}.json`.
- **`--selftest <report>`** (`desktop_app/selftest.py`): in-bundle checks —
  version, bundled locales (load/parity/resolve), scan, I10 folder+file gates,
  six-condition guarded delete (blocked/cancelled/deleted via real
  `send2trash`). Runs against the frozen exe and the installer output with the
  dev env off the `PATH`. Mirrored by `tests/test_desktop_selftest.py` with the
  Recycle Bin short-circuited (`FA_SELFTEST_FAKE_TRASH=1`). Classification
  harness mirrors `conftest.classification_neutral_env` (real machine env
  reclassifies everything otherwise).
- **Full suite from the wheel** in a fresh venv: built
  `folder_analyzer-3.0.0-py3-none-any.whl`, installed into a clean venv, CLI
  `folder-analyzer.exe` scan+quit works, `folder_analyzer`/`desktop_app`
  resolve from site-packages; pytest from a temp copy of `tests/`+`api/`+`web/`
  → **398 passed / 2 skipped** (identical to source; api/web imported from the
  source copy because the wheel intentionally does not ship them).
- **Engine frozen:** `git diff --stat` over `folder_analyzer/engine`,
  scanner.py, safety.py, security_guard.py, deleter.py from Phase 10 HEAD to
  the phase close is EMPTY.
- **Commits:** `c54efb3` (version 3.0.0 + locale package-data) → `c37fa63`
  (artifact self-test) → `e641116` (PyInstaller spec + Inno Setup script +
  build_desktop.ps1) → `docs(pkg)` close. Awaits explicit written acceptance.

### Recent repairs (12 issues)

Root-folder exclusion and scan-root deletion protection (CLI + API), clean EOF handling in the CLI, correct drill-down indexing, API scan state moved to `app.state` (opt-in reload via `FOLDER_ANALYZER_RELOAD=1`), `Field(default_factory=list)` for models, iterative `get_folder_size` (no recursion crash), `AppData\Roaming` flagged CAUTION, frontend uses detected drive labels and separates scanned vs drive stats, localized exports (CSV/HTML + API `lang`), valid setuptools `build-backend`, version consistency, expanded i18n.

### Tech stack

- Python 3.10+ (tested on 3.12)
- Rich (terminal UI), send2trash (Recycle Bin), psutil (disk info)
- FastAPI + Uvicorn (web), httpx (API testing)
- pytest — 398 tests passing (2 skipped) at Phase 11 close (397 at Phase 10 close)

### To continue development

```bash
cd /d C:\OPENCODE\Folder_Analyzer
python -m folder_analyzer --lang es --path C:\

# Web UI
python -m api

# Desktop UI (PySide6; install with: pip install -e ".[desktop]")
python -m desktop_app
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
- **Benchmark (measured, honest; evidence table in `docs/ARCHITECTURE.md` §6a):**
  gate alloc-peak **13.13–14.37 MiB** vs corrected 4′ (mean 12.01) = **+13.9%
  mean / +15.9% median** (worst-to-worst +14.0%), retained 7,400 @ +0% —
  within the 20% gate. **Uninstrumented direct wall-clock: Phase 4 0.143 s →
  Phase 5 0.782 s = +445% REAL classification/composition cost** (tracemalloc
  inflates BOTH phases ~6–7×, so instrumented 4.2–4.3 s is not the real number).
  The +445% is flagged as a Phase 8 (Performance & Scale) priority. The perf
  commit `96cdb16` was a **reactive fix**: the pre-fix state (`1a85a8c`)
  re-measured 8.66 s / 15.05–15.73 MiB alloc (+25–35% over the gate) → fixed to
  4.2–4.3 s / 13.1–14.4 MiB, mirroring Phase 3's transparent 2.109→1.054 report.
  RSS envelope 36.43–38.88 MiB (informational).
- **Docs:** `docs/ARCHITECTURE.md` (module map → Phase 5, KB wiring §2, phase-5
  baseline row §6), `docs/SAFETY.md` (I3/I10 → implemented, retention activation,
  §10/§11), `docs/ROADMAP.md` (Phase 5 → COMPLETE, status header), `CHANGELOG.md`.
- **Next:** Phase 6 — Exports v2 (export schema v2 with assessment fields +
  `analysis_state` markers; deterministic CSV/HTML/JSON).

## Phase 6 — Exports v2 (COMPLETED — formally APPROVED 2026-09-14)

- **Status:** reviewer formally approved on 2026-09-14; Phase 7 authorized with
  the final report at commit `445738a` (pushed). Verification points 1–3 all
  confirmed with evidence (recursive composition fix verified multi-level;
  `scan_result()` fold executed under the 8 patchers with 0 classifier/KB
  calls; `uncertain` + every producible key localized through actual CSV/HTML
  rows, EN+ES).

- **Delivered** (approved scope, commits `4b4b7a9` feat / `85f8fa8` test /
  `63f8cd7` bench):
  - `folder_analyzer/exporter.py` — `export_json_v2` / `export_csv_v2` /
    `export_html_v2`. All three consume **only** the `ScanResult` captured at scan
    time (`FolderAggregation`/`Assessment`); **zero** classifier/KB access.
    JSON v2: `schema_version=2` + scan metrics + `root_assessment` /
    `root_composition` + enriched tree (per-node `analysis_state`
    `files_analyzed`/`records_retained`/`assessment`/`composition`, children
    canonically sorted). CSV/HTML v2: + Recommendation / Confidence / Impact /
    Reason (localized via `explain.resolve_reason`) / Analysis State / Files
    Analyzed / Records Retained; top-500 rows sorted `(total_size desc,
    normalized path asc)`; scan root never a report row (v1 semantic). Cabinet
    decision: **v2 replaces v1 in CLI + API call sites; `export_*` v1 kept in
    the module, backward compatible** (`test_v1_exporters_preserved`).
    JSON stays language-neutral (enum `.value` + `reason_key`+`reason_params`);
    CSV/HTML carry the localized Reason text (identifiers, not localized labels,
    for Recommendation/Confidence/Impact/`analysis_state`).
  - **Determinism:** injectable `scan_date` (no `datetime.now()` in the
    serialized paper trail), canonical ordering (children by normalized path;
    CSV/HTML rows by size-then-path; `by_category` sorted), stabilization of all
    dict/field ordering ⇒ identical input ⇒ **byte-identical output**
    (SHA-256 hash-compare test over a fixed `scan_date`, all 3 formats).
  - **Zero-reclassification guardrail:** the export module carries no
    classifier/KB references (test inspects the exporting module's attribute
    table), and a wrapped-entry-point count test (8 canonical entry points in
    `kb` + `classifier`) asserts 0 calls across all three v2 exports.
  - **Wiring:** CLI `do_scan` now returns `(FolderInfo, ScanResult)`;
    `action_export` uses the v2 functions. API stores `app.state.last_scan_result`
    at scan time; `/api/export` uses the v2 exporters and returns 400 when the
    scan analysis is missing (test added). i18n: 7 new header keys (EN+ES).
  - Composition note (corrected during verification): per-folder
    `composition` is the **full recursive aggregation** — the folder's own
    direct analyzed bytes plus every descendant's — folded from the captured
    `FolderAggregation.composition` values at export time. Pure data
    arithmetic on scan-time data (no engine/classifier access);
    `root_composition.total_bytes == total_size == total_descendant_size`.
    `assessment` remains the engine's folder-level short-circuit verdict over
    the direct set (unchanged, I10-safe).
- **Suite:** 315 → **334 passed, 2 skipped** (+19: `tests/test_export_v2.py`
  +5 verification-point tests — recursive composition across levels,
  reason_key localization through actual CSV/HTML rows (EN+ES), item-demotion
  key set, producible-key audit; the zero-reclassification test now instruments
  the `scan_result()` fold — +3 in `tests/test_api.py`; `test_i18n.py`
  extended; `test_explain.py` + `uncertain`).
- **Benchmark (uninstrumented headline, pinned P-cores [`0,1`], 50k fixture):**
  scan-side delta of the v2 path = `t_fold`(`scan_result`) **0.494 ms =
  +0.11%** vs t_scan 0.470 s. **Export generation (its own honest number, after
  the recursive-composition fold): JSON 2.6 ms, CSV 0.9 ms, HTML 0.8 ms, total
  4.3 ms**; output bytes 59,862 / 7,509 / 30,081 (identical across runs). Gate
  (tracemalloc, deterministic): fold+export alloc-peak **0.26 MiB**, retained
  records 7,400 @ +0%. Runs:
  `benchmarks/results/phase6-export-r{1..3}.json` (gitignored).
- **Docs:** `docs/ROADMAP.md` (Phase 6 → COMPLETE, status header, §24 risk item 9
  context), `docs/ARCHITECTURE.md` (module map + §6 Phase-6 row),
  `CHANGELOG.md` [Unreleased].
- **Verification (reviewer, 2026-09-14):** point 1 confirmed + fixed —
  composition now the full recursive aggregation (multi-level test
  `test_composition_recursive_across_levels` proves
  `root_composition.total_bytes == total_size` and descendant-level
  `by_category`); point 2 emitted — `scan_result()` quoted and its fold now
  executed UNDER the 8-KB/classifier patchers with 0 calls (it is a pure in-memory
  fold, no classifier/KB); point 3 covered — `uncertain` registered EN/ES + every
  registered key proven localized through ACTUAL CSV/HTML rows in EN+ES +
  producible-key audit (no raw key can reach a reason cell).
- **Next:** awaits formal Phase 6 acceptance (`"Phase 6 approved, proceed to
  Phase 7"`). Phase 7 — Web UI + single-source i18n migration (`locales/*.json`),
  no further classification/composition changes (per approved scope).

## Phase 7 — Web UI + Single-Source i18n Migration (COMPLETED — submitted for acceptance)

- **Delivered** (approved scope — pushed; await `"Phase 7 approved, proceed to
  Phase 8"` before any Phase 8 work):
  1. **Single-source i18n** (`folder_analyzer/locales/en.json` + `es.json`):
     two namespaces per language — `ui` (ex-`i18n.STRINGS`) and `reasons`
     (ex-`explain.REASONS` → re-exported from `folder_analyzer/i18n`).
     CLI, exporters, API, and Web UI all read the same two files; no Python
     dict duplicates strings. `tests/test_locales.py`: EN/ES key parity per
     namespace, file shape/all-str, Python modules reading exactly the
     migrated files, Phase-6 reason-key registry (22 keys incl. `uncertain`)
     resolving non-raw in both locales.
  2. **API v2 surfaces** (`api/models.py`, `api/routes.py`): `/api/scan?lang=`
     now returns per-folder `AssessmentView` (localized `reason` via
     `explain.resolve_reason` from the single source) + recursive
     `composition`/`recursive_total` (mirrors the v2 JSON export shape);
     `GET /api/i18n?lang=` serves `{ui, reasons}` straight from the locale
     files; `GET /api/folder/files?path=&lang=` serves retained per-file
     `FileDict` rows with `evicted` flag.
  3. **Zero re-classification:** new read-only `Scanner.retained_records_for`
     (never re-analyzes; evicted folders → empty + `evicted: true`). The UI
     never calls `records_for` / re-scans.
  4. **Schema-v2 Web UI** (`web/`): recommendation / confidence / impact /
     localized reason per folder AND per retained file (drill-down panel);
     per-folder recursive total; all strings via `t()` / `data-i18n` from the
     locale files; language switch persisted in `localStorage`.
  5. **I10 in the UI:** `isActionEnabled(deletable, recommendation)` gates the
     FOLDER bulk action (REVIEW_FIRST ⇒ disabled) while an individually
     SAFE_TO_DELETE/HIGH file stays actionable inside a REVIEW_FIRST folder;
     server-localized `reason` is the only text rendered (no raw reason_key).
- **Suite:** 334 → **354 passed, 2 skipped** (+20: `tests/test_locales.py` +4,
  `tests/test_api.py` Phase-7 contract block +8, `tests/test_web_assets.py`
  +8). The Phase 6 CSV/HTML reason-coverage audit discipline was extended to
  the API rows (reason non-raw, `reason_key ∈ reasons`, no `{placeholders}`)
  and to executable JS (comment-stripped `reason_key`-absence + pinned-English
  literal absence + every `t()`/`data-i18n` key exists in both en/es files).
- **Benchmark (pinned P-cores [0,1], raw uninstrumented, 50k fixture):
  scan-side UNCHANGED** — `t_scan` 0.414 s (Phase 6: 0.470 s; faster,
  no regression), `t_fold(scan_result)` **0.492 ms = +0.12%** (Phase 6:
  0.494 ms), export generation JSON 2.4 / CSV 1.1 / HTML 1.2 ms (total
  4.7 ms), gate alloc-peak **0.26 MiB**, retained **7,400 @ +0%**, output
  bytes byte-identical at 59,862 / 7,509 / 30,081. No engine/classifier/KB/
  recommender changes (Phase 5 remains closed).
- **Docs:** `docs/ARCHITECTURE.md` (UI + API module map, Phase-7 benchmark
  row), `docs/ROADMAP.md` (Phase 7 → COMPLETE), `CHANGELOG.md` [Unreleased].
- **Commits:** `fb7259a` feat(i18n) single-source locales → `d7988d6` feat(api)
  v2 views + i18n + folder-files → `8e52976` feat(web) v2 UI + I10 gating →
  `docs` (this commit). Pushed to `origin/master`.
- **Next:** awaits formal Phase 7 acceptance. Phase 8 — Performance & Scale
  (full perf suite re-confirmed as a smoke benchmark here; the +445% Phase-5
  classification cost and unimplemented perf items stay Phase 8 scope). Do NOT
  begin Phase 8 without explicit approval.

## Phase 8 — Performance & Scale (COMPLETED — delivered 2026-09-14)

Approved by written charter: engine freeze LIFTED for this phase only for (a)
folder-prefix classification caching and (b) filename-only Tier-3 fast paths;
any other engine change out of bounds. Zero behavior change to outputs.

- **Delivered:**
  1. **O1 — `classifier.classify_scan` policy fast path:** `_policy_for` now
     reads a precomputed `_POLICY_TABLE` + shared `_UNKNOWN_POLICY` (frozen
     `CategoryPolicy`, value-safe) and the browser-marker bucket refinement is
     inlined — the doubled `_policy_for` per file (also inside
     `bucket_for_category`) is gone; public `bucket_for_category` unchanged.
  2. **O2 — bounded per-folder filename verdict cache** (`kb/`): `ScanFolderContext`
     gained `name_cache` (cap 256, enabled always); repeated names reuse the
     tier-2/3/4 result with the per-file `path` re-materialized. Validity: tiers
     2/3/4 verdicts depend only on folder parts + name; the tier-5 registry
     fallback is deliberately NOT cached (per-file path semantics stay exact).
     Proof: `tests/test_kb_cache.py` hits equal `kb.classify` for marker /
     extension / app-tree / registry-fallback / unknown shapes; spy test shows
     1 `classify_scan_name` call per distinct name, not per file.
  3. **Cancellation (core → API):** `scanner.ScanCancellation` (thread-safe
     event token, no FastAPI/Rich coupling), checked at folder granularity +
     every 4096 files; cancelled scans return the partial tree with
     `ScanResult.cancelled=True`; `POST /api/scan/cancel` wires the token via
     `app.state.last_scan_cancellation`.
  4. **Reproducible harness:** `run_smoke.py --affinity HEX` (explicit masked
     pinning), `kb_dispatch_us_per_file` / `classifier_us_per_file`, `--cancel`
     responsiveness probe; commands + noise band in `docs/ARCHITECTURE.md §7a`.
- **Core-selection note (corrected 2026-09-14):** the probe-ranked "fastest
  pair" is machine-state dependent — Phase-5/6/7 rows were mask 0x3 (`[0,1]`);
  at Phase-8 close the pair is 0xc00 (`[10,11]`). Closing comparisons are
  therefore SAME-MASK paired: Phase-7 state re-measured on 0xc00 = raw 0.36 s /
  export 0.3841 s. The original claim that mask 0x3 "now measures 2.1 s vs
  0.311 s" is **retracted** (see corrections section below) — no P-core
  identity drift exists; 0x3 at HEAD re-measures 0.324–0.351 s.
- **Benchmark (50k fixture, 0xc00, raw uninstrumented + gated):** smoke
  `t_scan` **0.309–0.311 s (−13.6%)**, export `t_scan` **0.3549 s (−7.6%)**,
  `t_fold` 0.424 ms; gate fold+export alloc-peak **0.26 MiB**, retained
  **7,400 @ +0%**, export bytes **byte-identical** 59,862 / 7,509 / 30,081;
  full-scan instrumented alloc-peak flat (12.88 vs 12.62–13.29 MiB). KB
  classification **2.4–2.7 µs/file dispatch, 2.1–2.3 µs/file full classifier**
  (Phase-5 close: 4.7 µs/file). Cancellation **≈8 ms to stop** after the
  request at 100 ms (17,505/50,000 files, 13/37 folders).
- **Suite:** 357 → **369 passed, 2 skipped** (+12: `test_kb_cache.py` +6,
  `test_cancellation.py` +5, `test_file_analysis.py` retention-budget gate +1).
- **Files changed:** `folder_analyzer/scanner.py`, `engine/classifier.py`,
  `engine/models.py`, `engine/kb/__init__.py`, `api/routes.py`,
  `benchmarks/run_smoke.py`, `tests/` (+2 new). Recommender / retention /
  safety / enums / explain and the KB tier tables (categories/apps/env/
  registry/content) untouched.
- **Docs:** `docs/ARCHITECTURE.md` (status, module map, Phase 8 row + §6c
  same-mask evidence + §7a commands), `docs/ROADMAP.md` (Phase 8 → COMPLETE),
  `CHANGELOG.md` [Unreleased].
- **Next:** awaits formal Phase 8 acceptance. Phase 9 — Desktop Architecture &
  Prototype (PySide6; needs written approval). Do NOT begin Phase 9 without
  it.

## Corrections (2026-09-14) — post-close, pre-acceptance blockers

- **Retracted: "mask 0x3 measures 2.1 s vs 0.311 s" (P-core identity
  drift).** Direct re-measurement on the same 50k fixture through the same
  harness shows the 2.1 s figure is not reproducible on either mask. Corrected
  matrix (raw uninstrumented `t_scan`): 09e38eb 0x3 = 0.425 / 0.412 s, HEAD 0x3
  = 0.324 / 0.324 / 0.351 s, 09e38eb 0xc00 = 0.357 / 0.358 s (+1 outlier 0.486),
  HEAD 0xc00 = 0.308 / 0.337 s. Within each state the masks overlap inside the
  ~15–30% single-run noise band; no sink is a core-placement property. The
  same-mask −13.6% / −7.6% comparisons in the Phase-8 section above are
  unaffected. Canonical text lives in `docs/ARCHITECTURE.md §6c`.
- **Dated marker for Phase-8 acceptance:** suite 369 passed → **375 passed,
  2 skipped** (+6 for the two blockers); cancellation is now surfaced end-to-end
  (API `ScanResponse.cancelled`, CLI PARTIAL notice, additive export markers,
  web UI localized notice) — see CHANGELOG correction entry.

## Actualización (2026-09-15) — evidence gap closed + pre-next-phase doc refresh

- **Evidence gap closed:** the three blocker test bodies and the corrected doc
  text (ARCHITECTURE §6c, CHANGELOG correction entry, SESSION corrections,
  ROADMAP Phase-8 block) were pasted verbatim from disk on request; the
  Phase-8 re-close report was accepted in substance by the user.
- **Documentation refresh (user-requested):** ROADMAP status header + Phase 8/9
  status blocks, ARCHITECTURE status header + module-map caption, and README
  (test counts, `/api/scan/cancel` endpoint, cancellation feature) brought to
  the current state. No code changed; nothing outside documentation was edited.
- **Current state at this date:** suite **375 passed / 2 skipped**; HEAD at the
  two blocker commits (`552625b`, `dfce81e`); Phase 8 blockers closed; formal
  written acceptance pending; next phase **NOT STARTED** and must not begin
  without explicit written approval.

## Phase 9 — Desktop Architecture & Prototype (delivered 2026-09-15; superseded by the approved Phase 10)

- **Approval:** the user restated the charter, the assistant returned an exact
  scope restatement (deliver / not-deliver / in-process rule / frozen-engine
  rule / close-proof plan), and the user confirmed it and authorized Phase 9.
- **ADR-001 (`docs/ADR-001-desktop-stack.md`, commit `2ea97dd`):** short record
  of the approved PySide6 choice vs PyQt6 / Tkinter / Tauri/Electron
  (ROADMAP §14), binding constraints: in-process core, no FastAPI/webview in
  desktop, core stays Qt-free, i18n single-source, Desktop-only PySide6 extra.
- **Prototype (commits `605bf90` scaffold, `59543e9` scan+table, `c130245`
  gated delete+cancellation):** `desktop_app/` — Qt-free `controller.py`
  (`scan`/`rows`/`action_enabled`/`delete_folders`), `worker.py` (`ScanWorker`
  QThread), `main_window.py` (picker → scan → localized assessment table →
  gated delete, EN/ES selector, PARTIAL notice). `pyproject.toml`:
  `desktop = ["PySide6>=6.6"]` extra + `folder-analyzer-desktop` script.
- **Safety invariants preserved:** every delete path = UI gate
  (`deletable && recommendation == safe_to_delete` per folder) →
  `validate_delete_target(scan_root)` → `revalidate` → `send2trash`; scan root
  excluded from rows and never deletable; containment enforced; I10 holds (SAFE
  `Data/cache` folder actionable beneath REVIEW_FIRST `Data`). Cancellation
  token → core `Scanner.scan` → `ScanResult.cancelled` → visible PARTIAL
  notice (never silent). i18n reuses `locales/{en,es}.json` (ui + reasons);
  three new parity-kept UI keys (`desktop_pick_folder`,
  `desktop_status_ready`, `desktop_delete_skipped`).
- **Tests (commit `329d90b`):** Qt-free controller units (`test_desktop_controller.py`)
  + offscreen Qt smoke (`test_desktop_smoke.py`, `QT_QPA_PLATFORM=offscreen`);
  shared `mixed_sandbox` fixture added to `conftest.py`. Suite **375 → 384
  passed, 2 skipped** (+9).
- **Frozen engines:** `folder_analyzer/engine/` (recommender, retention,
  safety, enums, explain, kb tables) and `folder_analyzer/classifier` untouched
  — Phase 9 consumed `ScanResult`/`Scanner.scan`/`ScanResult.cancelled`/
  `security_guard` read-only. Locale files gained only the three new UI keys
  (parity test green).
- **Manual validation:** prototype run offscreen against the real 50k
  `benchmarks/generated/fixture` (36 rows populated, localized reason text,
  `Scan complete: 42.33 GB across 50000 files`); GUI launch available via
  `python -m desktop_app` (or the `folder-analyzer-desktop` console script).
- **Status:** delivered and submitted for acceptance — awaiting the user's
  explicit written approval; no next-phase work before it.