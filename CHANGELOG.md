# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (2026-09-16 — Phase 11 Packaging & Installer)

- **Version 3.0.0 (R6).** `pyproject.toml`, `folder_analyzer/__init__.py` and
  `api/main.py` now declare `3.0.0`. **Deliberate version-ahead-of-tag
  sequencing, per ROADMAP §18:** the *string* is 3.0.0 while **no `v3.0.0` git
  tag exists yet** — the tag is applied by default only at Phase 12. This is
  not an inconsistency.
- **PyInstaller onedir bundle** (`packaging/FolderAnalyzer.spec`): desktop app
  only; `console=False`; entry `FolderAnalyzer.exe`. Output
  `dist/FolderAnalyzer/` (exe 2,442,001 B; tree 116,718,796 B / 172 files;
  measured). `folder_analyzer/` is consumed in-process (ADR-001); the core is
  not rearranged for the bundle.
- **Locales bundled** inside the artifact (`_internal/folder_analyzer/locales/
  {en,es}.json`): verified loadable from the frozen exe (127 keys per locale,
  EN/ES parity, strings resolve — `en col_name='Name'`, `es 'Nombre'`).
- **Installer (R2/R3):** Inno Setup 6 script `packaging/folder-analyzer.iss`
  → `dist/FolderAnalyzer-Setup-3.0.0.exe`; silent install/uninstall verified
  (install exit 0, installed tree 121,216,313 B, uninstall exit 0, dir
  removed); the installed output runs the self-test standalone (exit 0).
- **Unsigned installer (deliberate decision):** the setup is NOT code-signed,
  per the user's explicit "ship unsigned" decision. SmartScreen will show
  "Unknown Publisher" on first run (workaround: More info → Run anyway).
  Documented in README ("Desktop app — packaged build & installer").
- **Artifact self-test** (`desktop_app/selftest.py`, `--selftest <report>`):
  in-bundle verification of version, bundled locales, scan, I10 folder/file
  gates, and the six-condition guarded delete (`blocked` / `cancelled` /
  `deleted` via real `send2trash`) — run against the built exe AND the
  installer-installed output, with Python off the `PATH`. Mirrored in-repo by
  `tests/test_desktop_selftest.py` (Recycle Bin short-circuited).
- **Wheel stays the CLI path (R1):** `pip` wheel at 3.0.0 (locale
  `package-data` declared); fresh-venv install verified — import resolves from
  site-packages, CLI `folder-analyzer.exe` scan+quit works, and the **full
  suite runs from the wheel: 398 passed, 2 skipped** (source: 398 passed, 2
  skipped). `api/` + `web/` are imported from a source copy because they are
  not part of the wheel distribution (unchanged from v2.0.0).
- **Engine frozen throughout:** `git diff --stat` over
  `folder_analyzer/engine`, `folder_analyzer/scanner.py`, `safety.py`,
  `security_guard.py`, `deleter.py` between Phase 10 HEAD and the phase close
  is EMPTY.

### Changed (2026-09-16 — Phase 10 accepted)

- **Phase 10 formally approved and closed by the user** (2026-09-16) after the
  4-item residual evidence round: the export-timing artifact is now tracked as
  `benchmarks/results/export_p10_desktop.json` (`docs(bench)` commit `cb9afd3`,
  added past the ignore rule via `git add -f`); the 4 screenshots were proven as
  real committed PNG blobs in `5017420` (1,212–6,054 bytes); the temp-path
  evidence scripts were declared disposable one-off artifacts (the same facts
  are permanently covered by the committed pytest tests); and the integrity
  commitment was given in writing (raw output = actual fresh command output, or
  an explicit statement that verbatim evidence is unavailable). Suite remains
  397 passed / 2 skipped. Phases 11 and 12 remain NOT STARTED.

### Added (2026-09-15 — Phase 10 Desktop Application Complete)

- **Drill-down file view** (D1–D5): the desktop table now opens any folder row
  into a per-file view (`QStackedWidget`), sourced EXCLUSIVELY from
  `Scanner.retained_records_for` (zero re-classification, Phase 7 precedent);
  evicted folders show the folder-level-only notice (`records_evicted`) instead of
  fabricated file rows (D3). I10 gate applied per file row: `a.tmp`/`b.tmp` stay
  individually actionable beneath a REVIEW_FIRST parent, `notes.txt` does not.
- **Read-only reasons/details panel** (R1–R4): `desktop_app/details_dialog.py`
  shows name/size/recommendation/confidence/impact/reason from the same localized
  ScanResult fields; no delete control is present in the panel.
- **Export dialog** (E1–E4): format combo (JSON/CSV/HTML) + path + Browse + Save;
  the handler calls the core `export_json_v2`/`export_csv_v2`/`export_html_v2`
  (schema v2, deterministic), so `desktop_app/` contains zero export logic.
- **Settings — language only** (S1–S2): `desktop_app/settings.py` persists `lang`
  to `%APPDATA%/FolderAnalyzer/folder-analyzer-desktop.json` (stdlib json/pathlib;
  API/CLI/web/export unaffected); changes apply live and on next launch; invalid
  lang falls back to `en`; the config path is injectable for tests.
- **i18n** (I1–I3): single-source locale keys `col_name`, `desktop_back`,
  `desktop_details`, `desktop_no_files`, `desktop_open`, `desktop_settings`,
  `settings_language`, `btn_save`, `btn_browse` added to `en.json` and `es.json`
  (9 per language, parity-enforced). Live re-localization retranslates the table,
  drill-down, and open dialogs instantly.
- **Tests +13 (suite 384 → 397 passed, 2 skipped):** controller units
  (`file_rows` uses retained records + per-file I10, evicted folder → `[]` +
  `is_evicted` under `RetentionConfig(global_budget=1)`, `delete_files` shares the
  same guard path as `delete_folders`, `export_report` delegates to exporter v2 +
  determinism, `AppSettings` persistence) + offscreen smoke (drill-down I10 gates,
  evicted notice, live re-localization, details panel values + blank delete column,
  export dialog writes schema-v2 JSON, settings dialog applies/persists/relaunch).
- **Evidence for closure:** screenshots under `docs/screenshots/` (EN table,
  EN drill-down, ES details, ES settings); desktop-path export timing on the 50k
  fixture (`benchmarks/results/export_p10_desktop.json`); frozen-engine diff empty
  (`git diff --stat c2320ad..HEAD` over engine/scanner/safety/guard/deleter).

### Added (2026-09-15 — Phase 9 Desktop Architecture & Prototype)

- **ADR-001: PySide6 desktop stack** (`docs/ADR-001-desktop-stack.md`) — short
  record of the already-approved choice (ROADMAP §14): PySide6 selected over
  PyQt6 (GPL/commercial licensing), Tkinter (stdlib, limited) and
  Tauri/Electron (web shell, heavier). Core stays UI-independent; PySide6 is a
  Desktop-only optional dependency.
- **Desktop app prototype (`desktop_app/`, core in-process only, no FastAPI):**
  Qt-free `controller.py` (scan → localized assessment rows → I10 action gate →
  guarded delete), `worker.py` (`ScanWorker` QThread over the core `Scanner`),
  `main_window.py` (folder picker, path input, EN/ES language selector,
  Scan/Cancel/Send-to-Recycle-Bin, assessment table with localized
  recommendation / confidence / impact / reason / size / file count, explicit
  PARTIAL notice on cancelled scans). Entry points: `folder-analyzer-desktop`
  script + `python -m desktop_app`.
- **Deletion path wraps the six-condition guard on every delete:**
  `validate_delete_target(scan_root)` → `revalidate` → `send2trash`; the scan
  root and anything outside it are never deletable; I10 gate
  (`deletable && recommendation == safe_to_delete`) applied per folder, so a
  SAFE folder under a REVIEW_FIRST parent stays individually actionable.
- **PySide6 wired as optional extra:** `pyproject.toml` `desktop = ["PySide6>=6.6"]`.
- **Tests +9 (suite 375 → 384 passed, 2 skipped):** Qt-free controller unit
  tests (rows exclude scan root, I10 folder-gate, guarded delete via patched
  `send2trash`, pre-cancelled partial, single-source i18n labels) + offscreen
  Qt smoke tests (`QT_QPA_PLATFORM=offscreen`: window builds, scan populates
  the table and gates delete by selection, cancelled scan shows the partial
  notice). New shared fixture `mixed_sandbox` (SAFE cache folder under a
  REVIEW_FIRST parent) in `tests/conftest.py`.

### Changed (2026-09-14 — Phase 8 close corrections, pre-acceptance blockers)

- **Retracted: "mask 0x3 measures 2.1 s vs 0.311 s (P-core identity
  drift)."** The archival figure from the Phase-8 close is not reproducible on
  either mask. Corrected matrix (same 50k fixture, raw uninstrumented
  `t_scan`): 09e38eb 0x3 = 0.425 / 0.412 s, HEAD 0x3 = 0.324 / 0.324 / 0.351 s,
  09e38eb 0xc00 = 0.357 / 0.358 s (+1 outlier 0.486), HEAD 0xc00 = 0.308 /
  0.337 s. Within each state the masks overlap inside the ~15–30% single-run
  noise band; the same-mask −13.6% / −7.6% Phase-8 numbers are unaffected.
  Canonical text: `docs/ARCHITECTURE.md §6c`.
- **Cancellation surfaced end-to-end (charter constraint #3):** a cancelled
  scan is never presented as complete on any surface. API `ScanResponse` now
  carries `cancelled: bool`; the CLI announces an explicit localized PARTIAL
  notice instead of the success framing; v2 exports gain a visible
  cancellation marker (JSON `"cancelled": true` issued only when cancelled so
  normal-scan output stays byte-identical at schema v2; CSV localized marker
  row; HTML localized banner); the web UI renders a localized partial-notice
  on scan completion. New locale keys `scan_cancelled` / `scan_cancelled_detail`
  added to `en.json` and `es.json`.
- **Tests +6 (suite 369 → 375 passed, 2 skipped):** API surfaces
  `cancelled: true` in the scan response (concurrent cancel), JSON/CSV/HTML
  v2 cancelled-markers, CLI PARTIAL announcement, web-assets notice wiring.

### Changed (2026-09-15 — pre-next-phase documentation refresh)

- **Docs brought to current state (no code changed):** ROADMAP status header
  and Phase 8/9 status blocks (Phase 8 complete with blockers closed; Phase 9
  **NOT STARTED**, requires explicit written approval), ARCHITECTURE status
  header + module-map caption, README (suite 375 / 2 skipped, `/api/scan/cancel`
  endpoint, cancellation feature), SESSION dated entry summarizing the closed
  evidence gap and the refresh.

### Added (Phase 8 — Performance & Scale)

- **Hot-path optimization (engine):** `classifier.classify_scan` now calls
  `_policy_for` once (precomputed `_POLICY_TABLE` + shared `_UNKNOWN_POLICY`
  instance) and inlines the `browser`-marker bucket refinement, removing the
  doubled `_policy_for` + per-file policy construction from the 50k-file path;
  the public `bucket_for_category` is unchanged and remains the mapping truth.
- **Folder-filename verdict cache (KB):** `ScanFolderContext` gained a bounded
  256-entry `name_cache`; repeated filenames inside one folder reuse the
  tier-2/3/4 verdict with the current per-file `path` re-materialized. The
  tier-5 registry fallback stays uncached (per-file path semantics exact).
  Cache validity: tiers 2/3/4 verdicts depend only on folder parts + file name
  — proven byte-identical by `tests/test_kb_cache.py` vs `kb.classify` for
  marker, extension, app-tree, registry-fallback and unknown verdict shapes.
- **Scan cancellation (core → API):** `folder_analyzer/scanner.ScanCancellation`
  (thread-safe event token, no framework coupling). `Scanner.scan` accepts it
  and checks at folder granularity + every 4096 files; a cancelled scan returns
  the partial tree and `ScanResult.cancelled=True` (never silently complete).
  `POST /api/scan/cancel` (best-effort, idempotent) via
  `app.state.last_scan_cancellation`. Responsiveness: **≈8 ms** to stop a 50k
  scan after the cancel request (measured via `--cancel` probe).
- **Reproducible benchmark harness:** `run_smoke.py` `--affinity HEX` pins an
  explicit mask (skips the noisy P-core probe); new `kb_dispatch_us_per_file`
  / `classifier_us_per_file` metrics; `--cancel`/`--cancel-after` cancellation
  probe. Reference commands + noise band documented in ARCHITECTURE §7a.
- **Tests (+12, suite 357 → 369):** `test_kb_cache.py` (cache parity + cache-
  active proof + cache on t2-marker folders), `test_cancellation.py` (pre-
  cancelled empty partial, mid-scan partial consistency, token-never-fires,
  API cancel endpoint, no-token 400), retention-budget regression gate in
  `test_file_analysis.py`.
- **Benchmark results (50k fixture, `.affinity 0xc00` = cpus 10,11):** raw
  smoke `t_scan` 0.309–0.311 s (−13.6% vs re-measured Phase-7 state on the
  same pair), `run_export` `t_scan` 0.3549 s (−7.6%), KB dispatch 2.4–2.7
  µs/file + classifier 2.1–2.3 µs/file (Phase-5 close: 4.7), gate fold+export
  alloc-peak **0.26 MiB** + retained **7,400 @ +0%**, export output
  **byte-identical** (59,862 / 7,509 / 30,081 B). Full-scan instrumented
  alloc-peak flat (12.88 vs 12.62–13.29 MiB).
- **Docs:** ARCHITECTURE (status, module map, Phase 8 benchmark row + §6c
  same-mask evidence + §7a commands), SESSION, CHANGELOG.

### Added (Phase 7 — Web UI + Single-Source i18n Migration)

- **Single-source i18n** (`folder_analyzer/locales/en.json` + `es.json`):
  every translation string now lives in one place per language, in two
  namespaces — `ui` (ex-`i18n.STRINGS`, CLI/export/API/web) and `reasons` (ex
  `explain.REASONS`, the Phase 2/5/6 reason-key registry). `i18n.py` loads
  files at import and re-exports both; `explain.resolve_reason` reads the same
  source. No Python dict duplicates translation strings. CLI, exporters, API,
  and the Web UI (via `GET /api/i18n`) all consume the same two files.
- **Locale guarantees** (`tests/test_locales.py`): EN/ES key parity per
  namespace, file shape + all-`str` values, the Python modules reading exactly
  the migrated files, and every Phase 6 registered reason_key (22, incl.
  `uncertain`) resolving to non-raw text in both languages.
- **API v2 surfaces** (`api/`): `/api/scan?lang=` folder dicts now carry a
  localized `AssessmentView` (recommendation/confidence/impact/reason +
  `reason_key` for audit) and the recursive `composition`
  (`recursive_total`), mirroring the v2 JSON export shape; `GET /api/i18n?lang=`
  serves the single-source ui/reasons payload to the browser; `GET
  /api/folder/files?path=&lang=` streams the already-retained per-file records
  as localized `FileDict` rows with an `evicted` flag.
- **Zero re-classification (UI):** new read-only `Scanner.retained_records_for`
  serves only what the retention store already holds from the scan; evicted
  folders return an empty list + `evicted: true`. The UI never calls
  `records_for`/re-scans (Phase 6 principle).
- **Schema-v2 Web UI** (`web/`): table shows recommendation / confidence /
  impact / localized reason per folder AND per retained file (drill-down
  panel); per-folder recursive total; all strings from the locale files
  (`data-i18n` + `t()` lookups, language switch, `lang` persisted).
- **I10 item-vs-folder authority in the UI:** the FOLDER bulk-delete is gated
  by the folder's own assessment (`isActionEnabled(deletable, recommendation)`
  — REVIEW_FIRST ⇒ disabled); an individually SAFE_TO_DELETE/HIGH file inside
  a REVIEW_FIRST folder stays actionable. The API serves independent
  per-folder and per-file recommendations so the frontend implements I10
  without any folder-level assumption.
- **No raw reason_key in the rendered UI:** the API interpolates locale
  `reason` text server-side; `app.js` renders `reason` only (audit-test strips
  comments and asserts `reason_key` never appears in executable JS), with no
  hardcoded English literals remaining.
- **Tests** (`tests/test_locales.py`, `test_api.py` Phase-7 block,
  `test_web_assets.py`): locale parity/presence, localized-scan and
  folder-files contract surfaces, served `reason` non-raw (`!= reason_key`,
  no unsubstituted `{placeholders}`, key ∈ reasons), I10 gating-data rule
  mirrored from the UI predicate, frontend never-renders-reason_key + no
  English literals + every `t()`/`data-i18n` key present in both locale files.
  Suite grew **334 → 354 passed, 2 skipped** (+20).
- **Benchmark (Phase 7 smoke confirmation, pinned P-cores [0,1], raw
  uninstrumented, 50k fixture):** scan-side unchanged — `t_scan` 0.414–0.416 s,
  `t_fold(scan_result)` **0.492 ms = +0.12%** (Phase 6: 0.494 ms), export
  generation JSON 2.4 / CSV 1.1 / HTML 1.2 ms (total 4.7 ms), gate alloc-peak
  **0.26 MiB**, retained **7,400 @ +0%**, output bytes byte-identical at
  **59,862 / 7,509 / 30,081**. No engine/classifier/KB/recommender changes
  (Phase 5 remains closed).
- **Docs:** `docs/ARCHITECTURE.md` (UI + API module map, Phase-7 benchmark
  row), `docs/ROADMAP.md` (Phase 7 → COMPLETE), `SESSION.md`.

### Added (Phase 6 — Exports v2)

- **v2 exporters** (`folder_analyzer/exporter.py`, `export_json_v2` /
  `export_csv_v2` / `export_html_v2`): consume **only** the `ScanResult` collected
  at scan time — **zero** knowledge-base/classifier access during export
  (guardrail test). Enriched per-folder data: `analysis_state`, `files_analyzed`,
  `records_retained`, `assessment`, `composition`.
- **Composition semantics (verification point):** every node's `composition` is
  the full RECURSIVE aggregation (own direct bytes + every descendant's, folded
  from the scan-time `FolderComposition` values at export time); pure data fold,
  no engine access. `root_composition.total_bytes == total_size`. `assessment`
  unchanged (folder-level short-circuit over the direct set).
- **JSON v2 schema** (`schema_version=2`): top-level scan metrics
  (`scan_date`, `root_path`, `total_size`, `total_files`, `total_folders`,
  `files_analyzed`, `records_retained`, `inaccessible_count`, `folder_errors`),
  `root_assessment`/`root_composition`, and a recursive enriched `tree`
  (children canonically sorted). Language-neutral assessment payload
  (enum `.value` + `reason_key` + `reason_params`).
- **CSV/HTML v2:** new columns Recommendation / Confidence / Impact / Reason
  (localized via `explain.resolve_reason`) / Analysis State / Files Analyzed /
  Records Retained; top-500 rows sorted `(total_size desc, normalized path asc)`;
  scan root never a report row. HTML escapes paths/reasons (correctness fix).
- **Determinism:** injectable `scan_date`, canonical ordering, stable dict/field
  construction ⇒ identical input ⇒ byte-identical output (SHA-256 hash-compare
  test, all 3 formats).
- **Wiring:** CLI `do_scan` returns `(FolderInfo, ScanResult)`;
  API stores `app.state.last_scan_result` at scan time and `/api/export` returns
  400 when the analysis is missing. v1 `export_*` functions kept for backward
  compatibility (`test_v1_exporters_preserved`); v2 replaces v1 at the CLI/API
  call sites.
- **i18n:** 7 new EN/ES header keys (`col_recommendation`, `col_confidence`,
  `col_impact`, `col_reason`, `col_analysis_state`, `col_files_analyzed`,
  `col_records_retained`).
- **Explainability:** register `uncertain` (I3 item-level demotion key from
  `models.py Assessment.__post_init__`) EN+ES, closing a latent raw-key leak
  in `explain.resolve_reason`.
- **Tests** (`tests/test_export_v2.py`): schema + enrichment, canonical ordering,
  files-analyzed full coverage, localized ES CSV/HTML, byte-identical
  determinism (all 3 formats), zero-reclassification guardrail (module-reference
  inspection + 8 wrapped KB/classifier entry points; the `scan_result()` fold is
  now executed UNDER the patchers with 0 calls), recursive composition across
  levels, reason-key localization through ACTUAL CSV/HTML rows (EN+ES),
  item-demotion key audit, producible-key audit, v1 preservation. API tests:
  missing-analysis 400, JSON v2 schema on `/api/export`, `last_scan_result`
  stored. i18n test extended; `test_explain.py` `KNOWN_KEYS` + `uncertain`.
  Suite grew **315 → 334 passed, 2 skipped** (+19).
- **Benchmark (uninstrumented headline, pinned P-cores, 50k fixture):** scan-side
  delta of the v2 path = `t_fold(scan_result)` **0.494 ms = +0.11%** (n=1,
  pinned P-cores [0,1]). Export generation (own honest number, after the
  recursive-composition fold): JSON 2.6 ms, CSV 0.9 ms, HTML 0.8 ms, total
  4.3 ms; 59,862 / 7,509 / 30,081 B output (identical across runs). Gate
  alloc-peak fold+export **0.26 MiB**, retained 7,400 @ +0%. Runs
  `benchmarks/results/phase6-export-r{1..3}.json` (gitignored). New harness
  `benchmarks/run_export.py` reuses the pinned affinity methodology.
- **Docs:** `docs/ARCHITECTURE.md` (module map → Phase 6, §6 Phase-6 benchmark
  row), `docs/ROADMAP.md` (Phase 6 → COMPLETE, status header), `SESSION.md`.

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
- **Ex6 confidence resolution (Phase-5 close):** with the approved source supplied, the
  interim HIGH rationale (`d6ba116`) was checked against the source's own cross-example
  pattern — Ex4 (5% unknown) / Ex6 (0% unknown) / Ex7 (~5% unknown) all carry MEDIUM, so
  folder-level REVIEW_FIRST confidence does NOT track unknown-byte share. Ex6
  **reverted to the source's MEDIUM**: the value follows the source verbatim, folder-level
  derived confidence is re-stated as aggregate-verdict certainty over a heterogeneous
  composition (§2), and `derive_folder_recommendation`'s R2 branch now stamps
  `MEDIUM` (was HIGH) while the Downloads-policy floor (Ex8) and R1/R5 keep HIGH.
  Item-level confidence (§2) is unaffected. Docs: §2 folder-level clarification,
  §11 table row 6 + footnote, §24 risk item 8 reversion note.
- **Ex7 canonical row-7 correction (Phase-5 close):** §11 row 7 (`C:\Users | HIGH /
  DO_NOT_DELETE / HIGH`) corrected to the source's REVIEW_FIRST/MEDIUM. It had no live
  code path (`kb.classify("C:\Users")` → `unknown`; the USERPROFILE subtree resolves
  `user_profile` → USER_VALUE); "Protected" traced to the legacy `safety.py` CAUTION
  guard color, not the composition model. Aligned the recommender docstring (table rows
  6+7 — the row-6 HIGH was a missed remnant of the Ex6 reversion), added a canonical ex7
  composition test and a pinned Tier-1 known-folder boundary test (Downloads/Documents/
  Desktop/user_profile/app_data_local/app_data_roaming are never PROTECTED_CRITICAL;
  PROGRAMDATA is the one intentional protected member). Docs: ROADMAP §11 row + footnote,
  §24 risk item 9, `docs/SAFETY.md` §2.2. No classification code changed. Suite grew
**313 → 315 passed, 2 skipped**.

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