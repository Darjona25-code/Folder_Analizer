# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (Phase 5 — Recommendation Engine + Folder Composition + ScanResult)

- **Assessment pipeline wired into the scan** (`engine/classifier.py`): tied tiers
  0→5 through `eval_decision`-style policies into `Assessment`/`ScanAssessment`
  (frozen `slots` dataclasses). Items carry `detected_category`, three-axis
  values, `reason_key` (Phase-2 keys + `user_value`/`known_non_disposable`/
  `not_resolvable`/`protected_critical`), and a precomputed `CompositionBucket`.
  `NOT_RESOLVABLE` stays `None` and the aggregation normalizes it to
  `UNKNOWN`/`unknown` — the KB never fabricates assessments.
- **Folder composition** (`engine/recommender.py`): `CompositionBucket` starts at
  100% `UNKNOWN` and is split by real classification as the scan aggregates every
  file's bytes; `derive_folder_recommendation` applies roadmap §11 short-circuits
  R1–R5 with named `CompositionConfig` (0.85 / 0.10 / 0.15), R3 demotion for
  `unknown ≥ 0.25`, the Downloads policy floor (`REVIEW_FIRST`), oversize
  awareness (100 GB case), and empty-tree handling. Shares always sum to 100% of
  descendant bytes. Derived recommendations reuse the Phase-2 confidence gate —
  no SAFE without HIGH confidence.
- **ScanResult scope (I10):** every `FileEntry` shows its assessment and every
  `FolderAggregation` its derived assessment + composition. Item-level
  authority is preserved: `valid-item-SAFE/HIGH` beneath a folder-derived
  `REVIEW_FIRST` is still validated by the deletion guard (guarding only the
  folder-as-a-whole action).
- **Perf discipline:** scan path normalizes each path **once** (tier `classify`
  accepts a precomputed `_key`); tier modules cached in a lazy dict; Tier-2
  marker union fast-path; analyzer-side `ScanAssessment` keeps classification
  cheap (`bucket` precomputed, no `reason_params` dict for static keys);
  retention materializes full `Assessment`s only for the retained subset.
- **Tests** (`tests/test_classifier.py`, `tests/test_file_analysis.py`,
  `tests/test_i10_integration.py`, `tests/conftest.py`): `classification_neutral_env`
  + `scan_sandbox` fixtures (scan tests are immune to the real `%TEMP%`);
  8 canonical composition examples; NOT_RESOLVABLE→UNKNOWN; scan-record ⇄
  Assessment parity; scanner end-to-end metadata/aggregation/retention with real
  classification; I10 authority; suite grew **304 passed, 2 skipped**.
- **Benchmark (measured, honest):** Phase 5 pinned gate runs 4.204–4.310 s
  instrumented; gate alloc-peak **13.97 MiB** (representative delta
  **+16.3%** vs corrected baseline; retained_records
  7,400 @ +0%) — within the 20% gate. **Uninstrumented direct wall-clock is the
  real cost: 0.143 s (Phase 4) → 0.782 s (Phase 5) = +445%**, flagged as a
  Phase 8 (Performance & Scale) priority. (The instrumented numbers are inflated
  ~6–7× by tracemalloc for BOTH phases.) Evidence table in
  `docs/ARCHITECTURE.md` §6a; RSS remains informational envelope.
- **Phase-5 close optimization ("block Phase 6 until optimized"):** scan hot path
  restructured with exact-parity guarantees (`tests/test_kb_scan_parity.py`):
  folder-context tier pre-resolution (`kb.prepare_scan_folder` /
  `classify_scan_path` — prefix tiers 0/1/5 resolved once per folder, component
  tiers 2/4 plus extension 3 run per file), name-only fast paths where the folder
  carries no marker, a derived per-file key (no normpath/normcase per file), and
  frozen `ScanAssessment` memoization by (category, bucket). Measured uninstrumented
  wall **0.782 → 0.476 s (mean, n=6, −39%)**; KB classification pass 8.5 → 4.7
  µs/file; instrumented gate-scan 4.2 → 2.55 s. Suite grew **313 passed, 2
  skipped**.
- **Docs:** `docs/ARCHITECTURE.md` (module map → Phase 5, scanner flow, KB wiring,
  phase-5 baseline row), `docs/SAFETY.md`, `docs/ROADMAP.md` Phase 5 → COMPLETE.
- **Ex6 confidence resolution (Phase-5 close):** after the approved source document
  was supplied, the §11 canonical `Ex6 = NONE/REVIEW_FIRST/HIGH` value was confirmed
  as a **deliberate, documented correction** of the source draft's `MEDIUM` (approved
  2026-09-13) — routing through §24 risk item 8 with a confidence-independence-
  axiom justification (`unknown_pct = 0` ⇒ high classification certainty; REVIEW_FIRST
  is the R2/I7 policy floor, independent of certainty). No code or test change: the
  R2 branch already stamps HIGH, the composition test already asserts `ConfidenceLevel.HIGH`.
  The earlier "committed value governs" provenance framing is replaced by the
  explicit approved-correction note; Ex6 remains `NONE/REVIEW_FIRST/HIGH`.

### Added (Phase 4 — Knowledge Base, standalone / not wired)

- **Tiered knowledge base** (`folder_analyzer/engine/kb/`, roadmap §10; approved
  location beside the other engine modules): ordered path-classification dispatch
  that returns a single `KBResult(category, tier, confidence_hint, level, detail)`.
  Tiers run 0→5, first match wins:
  - **Tier 0** `known_paths.py` — critical/system paths; `_EXACT` (drive root,
    exact-match only, binary search over sorted tables) + `_TREE` (SystemRoot /
    System32 / SysWOW64 / Program Files / ProgramData / `$Recycle.Bin` / System
    Volume Information / Recovery — containment).
  - **Tier 1** `env_paths.py` — `USERPROFILE`/`APPDATA`/`LOCALAPPDATA`/
    `PROGRAMDATA`/`PROGRAMFILES`/`WINDIR`/`TEMP`/`TMP` + Known Folders
    (Downloads/Documents/Desktop/… via `SHGetKnownFolderPath`, ctypes), resolved
    in most-specific-first order and cached **once per scan session**.
  - **Tier 2** `categories.py` — component patterns (browser → dev → ai_ml →
    game → docker → cache; browser evidence precedes the generic cache bucket).
  - **Tier 3** `categories.py` — curated extension table (temp/system/documents/
    media/archives/databases/config, ~90 entries); evaluated before Tiers 4–5.
  - **Tier 4** `apps.py` — `app:ollama` / `app:docker` / `app:python` /
    `app:node` / `app:browser`, reached only when no earlier tier matched.
  - **Tier 5** `registry.py` — optional Windows Uninstall catalog (HKLM
    64/32-bit + HKCU), **batch-loaded once per session** (roadmap §10 convention),
    safe-empty on any failure, never a hard dependency.
- **Bounded content levels** (`content.py`, only via `kb.classify_content(path,
  level)`): Level 2 (≤512 B) magic-byte registry; Level 3 (≤4 KB) rare/justified
  SQLite windowed re-confirmation + Ollama-manifest detection (path must contain
  `ollama`+`manifests` and OCI JSON fields). No full-file read path anywhere;
  a >100 MB file is proved (instrumented) to consume ≤512 B / ≤4 KB.
- **Unknown stays unknown:** no tier match → `unknown` / `tier=None` /
  `confidence_hint=low`; `KBResult` has no assessment/recommendation fields — the
  KB never constructs `Assessment` objects (asserted by tests).
- **Session caches** reset via `kb.reset_session_caches()` (scan boundaries);
  count-proven single batch per session for Known Folder resolution and registry.
- **Memory discipline:** all tier tables are module-level constants loaded once
  (~tens of KB, <100 KB total); nothing KB lives in the scan hot path.
- **Tests:** `tests/test_knowledge_base.py` (31 tests: tier-by-tier correctness,
  Tier-0 exact-vs-tree + binary-search, dispatch first-match-wins incl. Tier-3
  short-circuit of Tier 4, caching counting proofs, bounded-read sparse-file
  proofs, unknown-stays-unknown). Suite grew **148 → 179 passed, 2 skipped**.
- **Scan-path regression check:** `scanner.py` is byte-identical to Phase 3; the
  KB is not imported by any scan/delete code. Six-run smoke benchmark
  `1.001–1.495 s` (best run at/under the Phase-3 baseline; spread is machine
  noise) — details + JSON artifacts in `docs/ARCHITECTURE.md` §6.
- **Docs:** `docs/ARCHITECTURE.md` (KB model §2 + module map + memory footprint +
  RSS trend status + Phase-4 benchmark row / artifacts), `docs/SAFETY.md`
  (categories-not-Assessments confirmation; L2/L3 implemented but standalone at
  scan time), `docs/ROADMAP.md` Phase 4 → COMPLETE.

### Added (Phase 3 — File Analysis & Data Model)

- **Per-file Level-1 metadata** (`folder_analyzer/scanner.py`, `engine/models.py`
  `FileEntry`): path, filename, extension, size, created/modified/accessed
  timestamps, stat attributes — collected during the existing traversal with
  **zero additional syscalls** (reuses the single `entry.stat()` per file; symlink
  flag from the DirEntry scandir cache). Records are `category="unknown"` /
  `assessment=None` — metadata only, no classification, KB, or content reads.
- **Data model** (`engine/models.py`): `AnalysisState`
  (DISCOVERED/ANALYZED/RETAINED), per-folder `FolderAggregation`
  (`files_analyzed`, `records_retained`, `total_descendant_size`,
  `by_impact`/`by_recommendation`/`by_confidence` shape, protected/unknown/
  user_data count+size, `app_ids`), whole-scan `ScanResult`.
- **Bounded prioritized retention** (`engine/retention.py`): configurable global
  budget (default 10,000) + per-folder cap (default 200); eviction priority
  non-safe → representative (one per folder/category) → largest → path. The
  non-safe relevance signal is inert in Phase 3 (implemented + tested, live in
  Phase 5). Eviction never reduces `files_analyzed`; evicted folders are
  re-analyzed on demand via `Scanner.records_for` (single-folder re-scan).
- **100%-analyzed invariant:** `files_analyzed` always equals 100% of accessible
  files, even when `records_retained` < files_analyzed due to eviction (proven by
  an explicit test).
- **Benchmark** (vs Phase 2 reference 0.919 s / 54,386 files/s / 50.54 MiB):
  Phase 3 = **1.054 s / 47,437 files/s / 59.75 MiB** (+14.7% time, within the
  20% gate), 7,400 retained records (default caps). Regression investigation
  documented in `docs/ARCHITECTURE.md` §6: naive all-record materialization was
  2.109 s / 105 MiB → fixed by lazy retention-only materialization.
- **Tests:** `tests/test_file_analysis.py` (12 tests: metadata extraction,
  zero-extra-syscall instrumented count, per-folder cap / global budget / cap
  zero, eviction priority incl. non-safe hook + representative sampler,
  100%-analyzed invariant, aggregation shape, on-demand re-analysis). Suite grew
  133 → **145 passed, 2 skipped**.
- **Docs:** `docs/ARCHITECTURE.md` scanner flow + file-analysis/retention model +
  benchmark table; `docs/SAFETY.md` content-analysis status — **Level 2 (magic
  bytes ≤512 B) and Level 3 (≤4 KB inspection) are explicitly NOT implemented**
  (Phase 4); classification/composition remain Phase 5.

### Added (Phase 2 — Safety Engine Model)

- **Three-axis safety model foundation** (`folder_analyzer/engine/`): `enums.py`
  — `SystemImpact` / `DeletionRecommendation` / `ConfidenceLevel` value spaces;
  `models.py` — immutable `Assessment` (impact, recommendation, confidence,
  `reason_key`/`reason_params`, `detected_category`, `app_id`, `is_user_data`,
  `is_temporary`) with the confidence gate (I9), UNKNOWN-impact (I3) and
  user-data (I7) floors enforced **at construction** — a
  `SAFE_TO_DELETE`-without-`HIGH`-confidence Assessment is structurally
  unrepresentable; demotions from SAFE also rewrite `reason_key`/`reason_params`
  to the demotion cause (I8 explainability coherence); `explain.py` —
  `reason_key` → localized EN/ES text (following the `i18n.py` pattern).
- **Safety invariants suite** (`tests/test_safety_invariants.py`): I1–I3 (item
  level), I7, I9 (exhaustive over all combinations), I10 scaffold + Assessment
  immutability; `tests/test_explain.py` for localized reason resolution. Suite
  grew from 110 to **129 tests** (2 privilege-dependent skipped). Benchmark on
  the unchanged scan path re-measured at ~0.92 s / ~54k files/s / ~50.5 MiB
  peak RSS — within run-to-run variance of the Phase 1 baseline.
- **Docs**: `docs/SAFETY.md` §6 documents the implemented three-axis model and
  construction-time confidence gate, §9 now a status table I1–I10, §11 scopes
  Phase 5 composition; `docs/ARCHITECTURE.md` adds `engine/` module map entries
  and updates the Phase-numbered status/steps.

### Added (Phase 1 — Deletion Security)

- **Canonical deletion guard** (`folder_analyzer/security_guard.py`): six-condition
  check (valid input → realpath+`normcase` canonicalization → component-boundary
  containment → root/ancestor protection → reparse-point integrity → final
  revalidation immediately before `send2trash`). Core, API, and CLI share the same
  guard; no interface can bypass it.
- **Append-only JSON Lines deletion audit log** (`folder_analyzer/audit.py`): every
  attempt (success/denied/deferred/failure, including denied) records original +
  canonical path, reason, risk; path overridable through `FOLDER_ANALYZER_AUDIT_LOG`.
- **Deletion boundary in API and CLI**: `/api/delete` returns `400 INVALID_PATH` /
  `400 UNRESOLVABLE_PATH`; CLI prints per-target deny/defer messages and counts
  deferred separately. New i18n keys (EN/ES).
- **Protected-path canonicalization fix**: protected/critical path checks now run on
  the canonical identity, closing a `\\?\`-prefix bypass for Tier-0/critical roots
  (`C:\Program Files`, `C:\$Recycle.Bin`, `C:\System Volume Information`,
  `C:\Recovery`, ...) under a containing scan root.
- **Smoke benchmark tooling** (`benchmarks/`): deterministic 50k-file fixture
  generator + scan benchmark. Phase 1 baseline recorded in `docs/ARCHITECTURE.md`
  §6 (0.816 s scan / 61,290 files/s / 53.65 MiB peak RSS).
- **Safety & architecture documentation**: `docs/SAFETY.md` (deletion-security
  foundation), `docs/ROADMAP.md` (approved master roadmap), `docs/ARCHITECTURE.md`
  scaffold.
- **Tests**: deletion-security suite (`tests/test_deletion_security.py`); baseline
  signature now 110 tests (2 privilege-dependent symlink tests skipped).

### Fixed (Phase 1 — security follow-up)

- `test_display_path_never_leaks_internal_prefix` previously asserted a vacuous term
  (`or True`); the internal-prefix-leak check is now strict.

### Fixed

- **Packaging**: `pyproject.toml` now declares a valid setuptools `build-backend`; `pip install .` works (previously failed with `BackendUnavailable`).
- **Version consistency**: `folder_analyzer.__version__` now reports `2.0.0`, matching `pyproject.toml` and the API.
- **Scan root self-listing**: the scanned root is excluded from "Top Folders" (CLI and API). It can never be deleted; its ancestors are protected too.
- **CLI crashes on EOF**: closed input at any prompt now exits cleanly ("Goodbye!") instead of raising an `EOFError` traceback.
- **CLI drill-down indexing**: the number you type in "View Details" maps to the currently displayed folder list, not the top-level list.
- **API global scan state**: `_last_scan_root` module global replaced with explicit `app.state.last_scan_root`. Endpoints return `400 "No scan performed yet"` until a scan; scan state is predictably per-process.
- **API reloader**: `reload=True` removed from the default server start; dev reload must be enabled via `FOLDER_ANALYZER_RELOAD=1` so state is never silently wiped.
- **Mutable model default**: `FolderDict.children` uses `Field(default_factory=list)` instead of a shared mutable default.
- **`get_folder_size` recursion**: replaced recursive traversal with an iterative stack (avoiding recursion-limit crashes on deep trees); `get_folder_size_recursive` kept as a compat alias.
- **`AppData\Roaming` risk**: now classified **CAUTION** (was SAFE).
- **Frontend drive/path handling**: the scan input uses the detected drive label (from `/api/drives`) instead of a hardcoded `C:\`, and scanned-folder stats no longer overwrite drive stats in the header.
- **Localized exports**: CSV headers and HTML report text are translated (EN/ES); the API export accepts a `lang` parameter.

### Added

- Tests: scanner root exclusion, safety Roaming CAUTION, deleter (protected paths, iterative size, root-blocked deletion), CLI (EOF, drill-down mapping), API (state lifecycle, root/ancestor protection, drive labels, localized exports), Pydantic model defaults. Test suite grew from 48 to **81 tests**.
- API: root and ancestor deletion protection; `/api/drives` now includes a `label`.

## [2.0.0] - 2026-07-25

### Added

- Web UI with Caza Bytes branding: FastAPI backend (`api/`) serving a static frontend (`web/`).
- REST API: scan, folders, stats, delete, export, drives.
- Treemap visualization for the CLI and web.
- Multi-language support (EN/ES).

## [1.0.0] - 2026-07-25

### Added

- Initial CLI disk space analyzer: multi-threaded scanner, Rich UI, ASCII treemap, safety risk levels, Recycle Bin deletion, JSON/CSV/HTML export.