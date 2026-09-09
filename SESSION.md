# Folder Analyzer - Session Continuation

If you need to continue this development session on another PC, open opencode and share this link:

**Link:** https://opncd.ai/share/a8LeCjC2

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