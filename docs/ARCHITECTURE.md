# Folder Analyzer — Architecture

Status: **Phase 8 — Performance & Scale** (hot-path optimization, cancellation,
reproducible benchmark harness). Phases 5 (recommendation engine + folder
composition), 6 (Exports v2) and 7 (Web UI + single-source i18n) are
closed/approved. This document
intentionally contains only the core/interface boundary, the current module map, the
CLI/Web/Desktop relationship, and the benchmark table. Performance (§ Phase 8) and
desktop (§ Phase 9/10) sections will be expanded in their respective phases; the
locales/UI map is current as of Phase 7.

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

## 2. Current module map (Phase 7)

| Module | Responsibility | Boundary |
|---|---|---|
| `folder_analyzer/scanner.py` | Multi-threaded disk scan → `FolderInfo` tree + `ScanResult`; per-file Level-1 metadata (zero extra syscalls); per-folder `FolderAggregation`; on-demand single-folder re-scan (`records_for`, drill-down only) + read-only `retained_records_for` (Phase 7, UI path — never re-analyzes). **Cancellation (Phase 8):** `ScanCancellation` token checked at folder granularity + every 4096 files; cancelled scans return a partial tree with `ScanResult.cancelled=True` (never silently complete) | Core |
| `folder_analyzer/deleter.py` | User-facing safe deletion flow (CLI-level) | Core (UI-agnostic; uses Rich only for CLI presentation) |
| `folder_analyzer/security_guard.py` | Six-condition canonical deletion guard | Core — security boundary |
| `folder_analyzer/audit.py` | Append-only JSON Lines deletion audit log | Core |
| `folder_analyzer/safety.py` | Risk levels + protected path detection (v2 model; superseded for assessment by the three-axis model) | Core |
| `folder_analyzer/engine/enums.py` | Three-axis value spaces: `SystemImpact` / `DeletionRecommendation` / `ConfidenceLevel` | Core — safety model |
| `folder_analyzer/engine/models.py` | Immutable `Assessment` (phase 2, confidence gate I9/I3/I7) + `FileEntry` / `FolderAggregation` / `ScanResult` (phase 3, metadata-only) | Core — safety model + data-model boundary |
| `folder_analyzer/engine/retention.py` | `RetentionConfig` + `RetainedFileStore`: bounded prioritized FileRecord retention (non-safe → representative → largest), lazy `FileEntry` materialization from raw `(DirEntry, stat)` pairs | Core — retention boundary |
| `folder_analyzer/engine/explain.py` | `reason_key` → localized EN/ES text (Phase 2 keys + Phase 5 item/folder reason keys); single-source since Phase 7 (reads the `reasons` namespace of `locales/*.json` via `folder_analyzer/i18n`) | Core |
| `folder_analyzer/engine/kb/` | Tiered knowledge base (roadmap §10): T0 critical/system paths, T1 env + Known Folders, T2 component patterns, T3 extension table, T4 app rules, T5 optional registry; `classify`/`classify_content` → `KBResult`; bounded L2/L3 content reads; per-session batch caching. Wired into the scan path since Phase 5 (single-normalize tier dispatch, cached tier modules). **Phase 8 fast path:** per-folder bounded filename verdict cache (`ScanFolderContext.name_cache`, cap 256) — repeated names reuse the tier-2/3/4 result with the current per-file `path`; tier-5 registry stays uncached to keep per-file semantics exact | Core — KB boundary |
| `folder_analyzer/i18n.py` | Single-source loader (Phase 7): loads `locales/{lang}.json` once at import and exposes `STRINGS[lang]` = `file["ui"]` and `REASONS[lang]` = `file["reasons"]`; `I18n.t()/set_lang` unchanged. No translation string lives in Python. | Core |
| `folder_analyzer/locales/` | `en.json` + `es.json` — the single source of truth for BOTH namespaces: `ui` (app/CLI/export/API/web strings) and `reasons` (the reason_key registry). EN/ES key parity enforced by `tests/test_locales.py`. | Core — data |
| `folder_analyzer/engine/classifier.py` | `classify_path`/`classify_scan`: KB result | policy | `Assessment` / lean `ScanAssessment` (bucket precomputed); successful pipeline only — `NOT_RESOLVABLE` returns `None` and aggregator normalizes to `UNKNOWN/a`; `fuse_folders_and_files`-style summary is compositional (see `recommender`) | Core — assessment boundary |
| `folder_analyzer/engine/recommender.py` | `derive_folder_recommendation`: roadmap §11 short-circuit R1–R5 with named `CompositionConfig` (0.85/0.10/0.15), R3 demotion (unknown ≥ 0.25), Downloads floor `REVIEW_FIRST`, 8 canonical examples, 100 GB case | Core — composition boundary |
| `folder_analyzer/utils.py` | Size formatting, drive default | Core |
| `folder_analyzer/treemap.py` | Treemap layout (presentation helper) | Core |
| `folder_analyzer/reporter.py` | Rich reporting helpers | Core |
| `folder_analyzer/exporter.py` | JSON/CSV/HTML export: v1 schema (backward compat) + **v2 (Phase 6, ScanResult-backed, deterministic, zero-reclassification; composition = full recursive aggregation)** | Core |
| `api/` | FastAPI app (`main.py`) + routes (`routes.py`) + Pydantic models (`models.py`) — web adapter. Phase 7 surfaces: `/api/scan?lang=` (per-folder localized `AssessmentView` + recursive `composition`/`recursive_total`), `/api/i18n?lang=` (single-source `{ui, reasons}`), `/api/folder/files?path=&lang=` (retained records, `evicted` flag, zero re-classification). Phase 8: `POST /api/scan/cancel` (best-effort, idempotent token on `app.state.last_scan_cancellation`) | Interface |
| `web/` | Static front-end (`index.html`, `js/app.js`, `css/style.css`): schema-v2 consumption (folder + per-file recommendation/confidence/impact/localized reason; drill-down panel; recursive total), locale-file lookups, I10 item-vs-folder gating (`isActionEnabled`), no raw `reason_key` rendered | Interface |
| `benchmarks/` | Fixture generator + smoke/export benchmarks (fixed baseline). Phase 8: `--affinity HEX` fixed-mask pinning (reproducible), KB µs/file measurement, `--cancel` cancellation-responsive probe | Tooling |
| `tests/` | pytest suites | Tooling |

Phase 3 wires the metadata + retention layer: the scanner records every accessible
file (analyzable) but materializes `FileEntry` objects **only for the bounded,
prioritized retained subset**. No classification is attached to records yet
(`category="unknown"`, `assessment=None`); the `by_*` aggregation dicts are structural
until Phase 5 populates them.

Phase 4 adds the Knowledge Base (`folder_analyzer/engine/kb/`) as a **standalone,
not-wired** component: it classifies *paths* (and, on explicit request, bounded content
prefixes) into a `KBResult(category, tier, confidence_hint, level, detail)` but nothing
in the scanner imports it yet — the scanner hot path is byte-identical since Phase 3
(verified: `folder_analyzer/scanner.py` unchanged between Phase 3 and Phase 4 close).

Phase 5 wires it: `classify_scan` is called per file during the scan; each record
carries its `ScanAssessment`/bucket; per-folder aggregation buckets bytes into
`CompositionBucket` and every folder gets a derived `Assessment` (roadmap §11);
`ScanResult`/`FileEntry`/`FolderAggregation` expose full assessments and
recommendations (I10: item-level `SAFE_TO_DELETE`+`HIGH` authority is preserved
beneath a folder's derived `REVIEW_FIRST`; the folder recommendation gates only the
folder-as-a-whole action).

Phase 7 (interface layer only — **no engine/classifier/KB change**): the Web UI
consumes the scan-time `ScanResult` through the API. Every per-folder `AssessmentView`
and per-file `FileDict` row is serialized with a **localized** `reason` interpolated
from the single-source locale files (`/api/i18n` is the same source the CLI and
exporters read). The UI never re-classifies: `/api/folder/files` reads only the
retention store via `Scanner.retained_records_for` (evicted folders report
`evicted: true` with empty rows), and I10 is implemented as an enable rule
(`deletable && recommendation == "safe_to_delete"`) applied independently to folder
bulk actions and to each file row.

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

### Knowledge-base model (Phase 4 as implemented)

The KB package `folder_analyzer/engine/kb/` classifies **paths** through an ordered
tier dispatch; each module exposes `classify(path) -> KBResult | None` and the one
dispatcher lives in `kb/__init__.py` (chosen over a separate dispatch module so the
tier order and the `classify`/`classify_content`/`reset_session_caches` surface are
single-sourced):

- **Tier 0** `known_paths.py` — critical/system paths. Two mechanisms: `_EXACT`
  (the drive root — matched **only against the path itself**, so it never flags every
  `C:\` descendant as system) and `_TREE` (SystemRoot, System32, SysWOW64, Program
  Files, ProgramData, `$Recycle.Bin`, `System Volume Information`, Recovery —
  containment). Both lists are sorted constant tables queried via binary search
  (`bisect`).
- **Tier 1** `env_paths.py` — `USERPROFILE`/`APPDATA`/`LOCALAPPDATA`/`PROGRAMDATA`/
  `PROGRAMFILES`/`WINDIR`/`TEMP`/`TMP` plus Known Folders (Downloads, Documents,
  Desktop, LocalAppData, RoamingAppData, ProgramData, Profile) resolved through
  `SHGetKnownFolderPath` (ctypes, win32 only). Ordering is **most-specific-first**:
  Downloads/Documents/Desktop and LOCALAPPDATA/APPDATA precede USERPROFILE, so a
  Downloads file is `downloads`, not the generic `user_profile`.
- **Tier 2** `categories.py` — component-name pattern sets, order
  browser → dev → ai_ml → game → docker → cache (browser evidence precedes the generic
  cache bucket so `Chrome\Cache` classifies as `browser`, the largest reclamation
  source). Matching is against whole path components (casefolded), never substrings or
  filenames.
- **Tier 3** `categories.py` — curated extension table (`temp`/`system`/`documents`/
  `media`/`archives`/`databases`/`config`; ~90 entries, material additions only).
  Evaluated after Tier 2 (path evidence before extension evidence) and **before**
  Tiers 4–5 — so first-match-wins means Tier 3 extension evidence short-circuits Tier 4
  app rules for mapped extensions (e.g. a `manifest.json` is `config`; its Ollama
  attribution is a Level 3 content check, not a path rule).
- **Tier 4** `apps.py` — app rules reached only when no earlier tier matched
  (`app:ollama`, `app:docker`, `app:python`, `app:node`, `app:browser`). App anchors
  (`.ollama`, `node_modules`, `site-packages`, …) are deliberately absent from Tier 2 so
  the dispatcher can reach Tier 4.
- **Tier 5** `registry.py` — optional Windows Uninstall catalog (`HKLM` 64/32-bit +
  `HKCU`), **batch-loaded once per scan session** (roadmap §10 convention; measured by a
  counting test). Any read failure yields an empty catalog — Tier 5 is never a hard
  dependency and degrades the dispatch to `unknown`.

**Dispatch contract:** tiers run 0→5; the first non-`None` result wins; if none match
the result is `category="unknown"`, `tier=None`, `confidence_hint="low"` — the KB never
fabricates a positive category from weak evidence. Because Tier 1 locations dominate
real Windows trees, Tiers 2/4/5 mainly classify paths **outside** known locations
(auxiliary/external drives), which is precisely the reclamation-scan space.

**Content levels** (`content.py`; only reachable via `kb.classify_content(path, level)`):
Level 2 (≤512 B) magic-byte registry; Level 3 (≤4 KB) rare, justified cases only — SQLite
header re-confirmation inside the window and Ollama-manifest confirmation (path must
contain `ollama`+`manifests`; checks OCI `schemaVersion`+`mediaType`/`layers`). There is
**no full-file read path anywhere in the KB**; a >100 MB file is proved by an
instrumented test to consume ≤512 B (L2) / ≤4 KB (L3). Unknown stays unknown at every
level.

**Session caches:** Known Folder resolution batches once per session and the registry
catalog batch-loads once per session; both reset via `kb.reset_session_caches()`
(scan boundaries) — verified by counting tests that mirror the Phase 3 syscall-count
pattern.

**Memory footprint (roadmap §10 report):** all tier tables are module-level constants
loaded once — T0 (≈20 entries) + T1 (16 ordered specs + resolved cache) + T2 (6 sets,
~40 tokens) + T3 (~90 extension keys) + T4 (~20 tokens) total **well under ~15 KB** of
table memory; the registry catalog is the only growth input (bounded by installed apps,
loaded once/session). Total KB footprint is in the **tens of KB (<100 KB)** — negligible
next to the scan's RSS (57–85 MiB). The KB adds **nothing** to the scan hot path until
wired in Phase 5 (benchmark §6).

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

### Corrected methodology (Phase 5 close; supersedes Phases 2–4 RSS comparisons)

The Phase 4 evidence report root-caused the 1.0–1.5 s / 58.8–78.3 MiB spreads on this
machine to **Windows hybrid P/E/LP-E core scheduling**: the OS places the scan across
cores with up to a 2.7× single-core throughput difference (P ~0.95–1.0 s, E ~1.6 s,
LP-E ~2.7 s for the 50k scan), and RSS-delta is a working-set sampling artifact whose
±30% noise floor exceeds the 20% gate tolerance. From Phase 5 the benchmark harness:

- **Pins the process to the fastest (P) cores** (probed each run by timing a fixed
  CPU-bound workload per logical CPU; `SetProcessAffinityMask` /
  `os.sched_setaffinity`) and caps scan workers to the pinned set, so scan times are
  comparable phase-over-phase.
- **Gate metrics = tracemalloc alloc-peak + retained_records** (deterministic,
  code-attributable). **Peak RSS is demoted to an informational envelope metric** —
  reported, never a hard gate.

| Phase | SCAN TIME (s) | FILES/S | GATE: ALLOC PEAK (MB) | GATE: RETAINED | ENVELOPE RSS (MB) | NOTES |
|---|---|---|---|---|---|---|
| 1 | **0.816** | **61,290** | 19.44 | n/a (Phase 3) | **53.65** | **original baseline** — 50,000 files, 37 dirs, 45,451,138,200 B fixture (unpinned; historical) |
| 2 | 0.919 | 54,386 | 19.32 | 0 | 50.54 | **Phase-3 reference baseline** (unpinned; historical) |
| 3 | 1.054 | 47,437 | 21.85 | 7,400 | 59.75 | Level-1 metadata + bounded retention (unpinned; historical) |
| 4 | 1.001–1.495 | 33,455–49,973 | 20.6–29.1 | 7,400 | 58.8–78.3 | KB added but **not wired** (`scanner.py` byte-identical to Phase 3). Spread was core-scheduling noise (see corrected methodology above) |
| **4′** | **0.985–1.006** (5 runs; ±2.1%) | ~49,700 | **11.64–12.60** | **7,400** | 31.96–34.21 | **CORRECTED Phase-4 baseline (Phase 5 harness): pinned to P-cores [`0,1`/`10,11`], gate = alloc-peak + retained.** Supersedes the noisy RSS-based rows above as the reference for all future phases. Runs: `benchmarks/results/baseline-phase5-pinned-r1..r5.json` |
| **5** | 4.204–4.310 (4-run) | ~11,600–11,900 | **13.13–14.37** (4 runs) | **7,400** | 36.43–38.88 | **Phase 5: recommendation engine (Assessment) + folder composition wired into the scan path**, plus classifier + KB module caching and path-normalize hoisting (all instrumented). Representative gate deltas vs 4′ (mean 12.01): **+13.9% (mean-to-mean) / +15.9% (median)**; best-to-best +12.8%, worst-to-worst +14.0% — within the 20% gate. (A coincidental max-vs-min pairing reached +20.6%; repeated clean runs show it is the noise band, not a stable condition — see §6a.) **Uninstrumented (direct wall-clock): Phase 4 0.137–0.151 s → Phase 5 0.778–0.787 s = +445% (5.5×) REAL cost.** tracemalloc inflates *both* phases ~6–7× (metadata scan 0.985–1.006 s instrumented vs 0.14 s plain), so instrumented wall is not interpreted as real cost. The +445% is genuine new classification/composition work **flagged as a Phase 8 (Performance & Scale) priority** — see §6a. Runs (locally, `benchmarks/results/` gitignored): `benchmarks/results/phase5-pinned-r{1..3}.json`, `phase5-pinned.json`, plus 4 clean remeasures. |
| **6** | 0.470 (uninstrumented; 0.494 ms `scan_result` fold added) | ~119,000 | fold+export **0.26** | **7,400** | n/a | **Phase 6: Exports v2 — no scanner hot-path change.** v2 exporters consume the collected ScanResult only; scan-side delta = `Scanner.scan_result()` fold **0.494 ms = +0.11%** (uninstrumented, pinned P-cores [`0,1`], 50k fixture). **Export generation (own honest number, after the recursive-composition fold): JSON 2.6 ms / CSV 0.9 ms / HTML 0.8 ms (total 4.3 ms)**; output 59,862 / 7,509 / 30,081 B, byte-identical across runs. **Composition fields are the full recursive aggregation** (`root_composition.total_bytes == total_size`), folded from scan-time `FolderComposition` values — no engine access. Runs: `benchmarks/results/phase6-export-r{1..3}.json` (`benchmarks/run_export.py`). |
| **7** | 0.414 (uninstrumented) | ~120,655 | fold+export **0.26** | **7,400** | 16.32 | **Phase 7: Web UI + single-source i18n — NO scan hot-path change (engine/classifier/KB untouched).** Locale files load once at import. `t_scan` 0.414–0.416 s, `t_fold(scan_result)` **0.492 ms = +0.12%** (Phase 6: 0.494 ms), export generation JSON 2.4 / CSV 1.1 / HTML 1.2 ms (total 4.7 ms), gate alloc-peak **0.26 MiB**, retained **7,400 @ +0%**, output bytes byte-identical at 59,862 / 7,509 / 30,081. UI/per-file reads go through read-only `Scanner.retained_records_for` (zero re-classification) and `/api/i18n` serves the same locale files the CLI/exports use. |
| **8** | **0.309–0.311** (uninstrumented, `--affinity 0xc00`) | ~160,600 | fold+export **0.26** | **7,400** | 16.5 | **Phase 8: Performance & Scale — hot-path optimization + cancellation + reproducible harness.** O1 single `_policy_for` + inlined bucket (`classifier.classify_scan`), O2 bounded per-folder filename verdict cache (`kb`), `--affinity HEX` fixed-mask pinning. Raw smoke `t_scan` 0.309–0.311 s on the machine's fastest pair (mask 0xc00 = cpus 10,11); **paired same-mask re-run of the Phase-7 code state: 0.36 s smoke / 0.3841 s export → −13.6% / −7.6%** (the archival 0.414 row was mask 0x3 = cpus 0,1; an early Phase-8 reading claimed 2.1 s on that mask — **retracted and corrected 2026-09-14 in §6c**: 0x3 re-measured 0.324–0.351 s at HEAD, no P-core identity drift). Classification measured **KB dispatch 2.4–2.7 µs/file, full classifier 2.1–2.3 µs/file** (Phase-5 close: 4.7). Cancellation: **≈8 ms to stop** after `POST /api/scan/cancel` at 100 ms (17,505/50,000 files, 13/37 folders), partial `ScanResult.cancelled=True`. **Byte-identical**: exports 59,862 / 7,509 / 30,081 B unchanged; 369 tests green (357 prior + 12 new). Evidence: `benchmarks/results/smoke_p8_*.json`, §6c. |

### 6a. Performance evidence for the Phase 5 close (reviewer-required remeasure)

Direct, unmassaged measurements (pinned P-cores, deterministic 50k fixture), re-run
2026-09-13 at code states `7bacf54` (Phase 4), `1a85a8c` (pre-perf Phase 5),
`bc6f733`/HEAD (Phase 5).

| Measurement | Phase 4 (`7bacf54`) | Phase 5 (HEAD) | note |
|---|---|---|---|
| runner scan, tracemalloc ON | 0.983, 1.002 s | 4.204–4.310 s → **2.546 s (optimized)** | harness gate runs |
| GATE alloc-peak, tracemalloc ON | 12.49, 12.61 MiB | 13.13–14.37 MiB (n=4) → **13.97 MiB (optimized)** | mean 13.68 vs baseline mean 12.01 = **+13.9%** (optimized reading +16.3% — within the 20% gate) |
| runner scan, tracemalloc OFF | 0.151, 0.137, 0.142 s (mean 0.143) | 0.787, 0.778, 0.783, 0.779 s (mean 0.782) → **0.435–0.516 s (mean 0.476, n=6, optimized)** | **real wall-clock: 0.143 → 0.782 s = +445% → 0.476 s = +233%; Phase-5-close optimization cut the classification pass ~half (−41% wall from 0.782, KB pass 8.5 → 4.7 µs/file)** |
| pre-perf Phase 5 (`1a85a8c`), tracemalloc ON | — | 8.656, 8.667 s | alloc 15.05, 15.73 MiB → **crossed the >20% gate** vs 4′ (up to +35%) and drove `96cdb16` (reactive perf fix, like Phase 3's 2.109→1.054) |

Optimization applied at Phase-5 close ("Block Phase 6 until optimized") before Exports v2
(started at the corrected evidence set): (1) **folder-context scan classification** —
`kb.prepare_scan_folder` resolves the folder-transitive prefix tiers (0/1/5) once per
folder; `classify_scan_path` reuses that context per file with exact per-file equality
(`tests/test_kb_scan_parity.py`); (2) **name-only fast paths** — when a folder carries no
Tier-2/Tier-4 marker the per-file component scan collapses to the filename
(`classify_scan_name`); (3) **derived file key** — `file_key = ctx.folder_key + os.sep + name.lower()`,
no normpath/normcase per file; (4) **frozen ScanAssessment memoization** by
(category, bucket) — per-file dataclass construction (and its allocation peak) removed for
identical verdicts; the shared instances are immutable (I10 reads fields only).

Findings: (1) tracemalloc itself inflates *both* inputs ~6–7× (the Phase-4 metadata
scan is 0.985–1.006 s instrumented but 0.137–0.151 s plain), so instrumented wall
time is an instrumentation artifact; gate decisions use alloc-peak + retained.
(2) The real Phase-5 cost was **+445% wall time (0.78 s absolute for 50k files,
~13 µs/file)**; the optimization brought it to **+233% (0.476 s, ~9.5 µs/file)** — the
50k fixture is adversarial (no viable extension/marker for a large share of files, so
every tier exhausts); even so the residual is now dominated by the per-item
materialization floor (one `ScanAssessment` verdict per file is required by I10 item
authority; shared instances are reused, not eliminated). (3) alloc-peak noise:
baseline n=5 spans 11.64–12.60 (±4%), Phase 5 n=4 spans 13.13–14.37 (±4.5%);
no single-phase reading vs the opposite phase's best/worst exceeds +14%
(worst-to-worst) — the +20.6% figure was a max-vs-min coincidental pairing.

### 6b. Folder-level confidence gate — currently-unreachable structural invariant

The folder-level confidence gate (I9 applied to `derive_folder_recommendation`'s output)
is a **structural invariant guard, not currently reachable through any real classification
path**. The gate fires when an `Assessment` with `recommendation=SAFE_TO_DELETE` carries
`confidence < HIGH` at construction (`models.py:86`). In the current KB/classifier model,
every item reaching the DISPOSABLE composition bucket does so via a pipeline verdict of
`recommendation=SAFE_TO_DELETE + confidence=HIGH` (classifier `bucket_for_assessment` routes
through `bucket_for_category`; the DISPOSABLE `CATEGORY_POLICY` entries — `temp`, `cache` —
at classifier.py:121-128 carry `confidence=ConfidenceLevel.HIGH`).
Since DISPOSABLE evidence is therefore always HIGH, `derive_folder_recommendation`'s R5
branch stamps `confidence=cfg.confidence_gate` (defaults to HIGH), and the constructor gate
is trivially satisfied.

The gate is validated with *synthetic* non-default `CompositionConfig(confidence_gate=MEDIUM/LOW)`
tests (`test_folder_confidence_gate_demotes_r5_eligible_safe_to_review`,
`test_folder_safe_never_carries_below_high_confidence_under_default_gate`) that prove the
mechanism fires at construction and that the pipeline cannot produce SAFE+non-HIGH under
defaults. This must not be treated as "validated by real data" — the gate becomes meaningful
only if a future KB tier or classifier change introduces MEDIUM/LOW-confidence
positive-disposable-evidence classifications. The test suite treats the structural invariant
as a regression guard, not a live code path.

> **RSS trend watch (Phase 5 close):** the historical Phase-1–4 rows used RSS-delta,
> which is a core-scheduling/working-set artifact on this hardware (±30% noise is
> larger than the 20% gate). The corrected methodology measures the two
> deterministic gate metrics (alloc-peak, retained) going forward; the Phase-4
> corrected baseline is **alloc 11.64–12.60 MiB, retained 7,400**, envelope RSS
> 31.96–34.21 MiB. The KB tables (~tens of KB, <100 KB total), session caches and
> the per-file classification records are loaded/alive in the scan process from
> Phase 5 (classifier wiring); their footprint is captured in the Phase-5 alloc-peak
> rows.

Regression policy: a `>20%` regression vs the corrected baseline **on the gate metrics
(alloc-peak, retained_records)** is a **phase-closing gate** (stop → investigate →
fix/justify → re-run; do not close until resolved or explicitly user-overridden and
documented). Envelope RSS is informational. See `docs/ROADMAP.md §15/§22`.

### 6c. Phase 8 performance evidence (direct, same-mask comparisons)

Re-run 2026-09-14 on the deterministic 50k fixture. Cross-phase wall-clock rows
use the same `--affinity` mask on both sides so core placement cannot distort a
delta. Probe ranking is re-evaluated every session by `_probe_fast_cores` and is
machine-state dependent (Phase-5/6/7 close sat on `[0,1]` = mask 0x3; Phase-8
close on `[10,11]` = mask 0xc00) — **there is no stable P-core identity drift.**
> **Dated correction (2026-09-14):** the Phase-8 close first claimed mask 0x3
> "now measures 2.1 s vs 0.311 s on 0xc00" (P-core identity drift). That figure
> is **retracted**: it is not reproducible on either mask. Direct re-measurement
> through the same harness shows both masks inside the same band, so the delta
> was a single transient reading, not a core-placement property. Corrected
> matrix (same 50k fixture, raw uninstrumented `t_scan`):

| mask | 09e38eb (pre-optimization state) | HEAD (Phase 8) |
|---|---|---|
| 0x3 (cpus 0,1) | 0.425 / 0.412 s | 0.324 / 0.324 / 0.351 s |
| 0xc00 (cpus 10,11) | 0.357 / 0.358 s (+1 outlier 0.486) | 0.308 / 0.337 s |

Pairwise means: 09e38eb 0x3 **0.419 s** ↔ HEAD 0x3 **0.333 s → −20.4%**;
09e38eb 0xc00 **0.358 s** ↔ HEAD 0xc00 **0.323 s → −9.8%**. Within either state
the masks overlap (HEAD: 0x3 0.324–0.351 vs 0xc00 0.308–0.337); single-run
`t_scan` jitter is ~15–30%, so no mask "wins" outside the noise band and core
selection is an implementation detail, not a correctness dimension. The Phase-8
close below compares the same 0xc00 pair on both states; `--affinity 0xc00` is
the closing-run convention (commands in §7).

| Measurement (50k fixture, same pair 0xc00 unless noted) | Phase 7 state (re-measured) | Phase 8 (HEAD) | delta |
|---|---|---|---|
| `run_export` t_scan, uninstrumented | 0.3841 s | 0.3549 s | **−7.6%** |
| `run_smoke` t_scan, uninstrumented | 0.360 s | 0.309–0.311 s (n=3) | **−13.6%** |
| `run_export` t_fold (`scan_result`) | 0.411 ms | 0.424 ms | **+3.2% (two readings, within noise)** |
| gate: fold+export alloc-peak | 0.26 MiB | 0.26 MiB | **0%** |
| gate: full-scan alloc-peak (instrumented) | 12.62 / 13.29 MiB | 12.88 / 12.88 MiB | flat (±2%) |
| gate: retained records / export bytes | 7,400 / 59,862·7,509·30,081 | 7,400 / 59,862·7,509·30,081 | **0% / byte-identical** |
| KB classification cost (µs/file) | 4.7 (Phase-5 close) | KB dispatch **2.4–2.7**, classifier **2.1–2.3** | ~2× faster |
| cancellation responsiveness | n/a | **≈8 ms** (107.5 ms stop with 100 ms cancel timer) | new metric |

Noise band: raw `t_scan` jitters ~15–30% single-run (HEAD: 0x3 0.324–0.351,
0xc00 0.308–0.337); an earlier "±1% across consecutive runs" framing came from a
short same-pair sequence and is superseded by the corrected matrix above.
Instrumented wall is inflated ~6× by tracemalloc (1.9 s vs 0.31 s raw) and is
not interpreted as real cost, exactly as documented in §6a. `t_fold` 0.411 →
0.424 ms = **+3.2%** (scan-side 0.107% → 0.119% of t_scan) — a two-reading delta
inside the noise band, reported honestly as consistent-with-flat. The scan
hot path and the name cache are output-neutral: the 8 canonical composition
examples, the `test_kb_scan_parity` byte-parity suite, and the byte-identical
export SHA-256 (`test_byte_identical_determinism`) all pass unmodified on the
optimized code. `git diff HEAD~1 --stat` for this phase touches `scanner.py`,
`engine/classifier.py`, `engine/models.py`, `engine/kb/__init__.py`,
`api/routes.py`, `benchmarks/`, and `tests/` only — the recommender, retention,
safety, enums, explain and KB tier tables (categories/apps/env/registry/content)
are untouched.

## 7. Reference environment

- **OS:** Windows 11 Pro 24H2 (build 26200), 64-bit (`Windows-11-10.0.26200-SP0`)
- **Python:** 3.12.10
- **Hardware:** developer laptop (see machine specs at Phase 1 close)
- **Fixture:** `benchmarks/generated/fixture` — 50,000 files, 37 dirs,
  45,451,138,200 B nominal size, seed `20260101` (sparse files; see `gen_fixture.py`).
- **JSON artifacts:** `benchmarks/results/smoke-phase1.json` (baseline),
  `smoke-phase2-rerun.json` (Phase-2 reference), `smoke-phase3-rerun2.json` (Phase 3);
  Phase 4 runs are recorded in `benchmarks/results/smoke-phase4-r1..r6.json`.
  **Corrected Phase-4 baseline (Phase 5 harness):** `benchmarks/results/baseline-phase5-pinned-r1..r5.json`.
  Phase 8: `smoke_p8_gated_run1.json`, `smoke_p8_raw_cancel.json`,
  `smoke_p8_raw_cancel2.json`, `smoke_p8_fixed_run1.json`
  (`benchmarks/results/` is gitignored).

### 7a. Phase 8 benchmark commands (copy-pasteable)

All runs pin the whole process to the machine's fastest core pair (this reference
machine and this closing session: cpus `10,11`, mask `0xc00`) so phase-over-phase
numbers are reproducible. The `--affinity` flag pins an explicit mask and skips the
noisy core probe — use it for every closing run; record the mask next to the numbers.

Fixture once:

    python benchmarks/gen_fixture.py --out benchmarks/generated/fixture

Uninstrumented scan smoke (headline cost; includes KB µs/file + optional cancel):

    python -m benchmarks.run_smoke --path benchmarks/generated/fixture --affinity 0xc00 --no-tracemalloc --cancel

Gated smoke (tracemalloc alloc-peak; ~6× inflated wall, gate = alloc-peak + retained):

    python -m benchmarks.run_smoke --path benchmarks/generated/fixture --affinity 0xc00

Export benchmark (t_scan / t_fold / export-generation / fold+export gate / bytes):

    python benchmarks/run_export.py --path benchmarks/generated/fixture

The smoke metrics `kb_dispatch_us_per_file` (raw `classify_scan_path` dispatch)
and `classifier_us_per_file` (`classify_scan`, incl. policy/bucket/record assembly)
are measured over every fixture file with one `ScanFolderContext` per parent folder
(the real scan shape, filename cache active), tracemalloc OFF. The `--cancel` probe
measures `stop_delay_ms` from `ScanCancellation.cancel()` at `--cancel-after` s
(default 0.10): the scan stops at the next folder boundary / 4096-file checkpoint.

Any change of environment that legitimately shifts the baseline must be documented with
justification — a new baseline is never established silently.