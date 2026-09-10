# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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