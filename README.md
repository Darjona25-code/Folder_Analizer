# Folder Analyzer

A disk space analyzer by **Caza Bytes** that scans drives, reports folder sizes, and safely frees disk space. Available as a Web UI or as a standalone `.exe` — no Python installation required for end users.

## Features

- **Web UI** — Dark-themed interface accessible at `localhost:8000`
- **Standalone .exe** — Built with PyInstaller, no Python needed
- **Fast multi-threaded scanning** — Uses `ThreadPoolExecutor` to scan drives quickly
- **Expandable folder details** — Click any row to drill into subfolders with tree-view indentation
- **Safety system** — Color-coded risk levels (CRITICAL / CAUTION / SAFE) to protect system folders
- **C: drive protection** — System folders (`C:\Windows`, `C:\Program Files`) are always blocked from deletion
- **Safe deletion** — Sends files to Recycle Bin (recoverable) instead of permanent delete
- **Export reports** — Save scan results as JSON, CSV, or a visual HTML report

## Quick Start (End Users)

Download `FolderAnalyzer.exe` from the [Releases](https://github.com/Darjona25-code/Folder_Analizer/releases) page and run it. Your browser will open automatically.

## Developer Setup

```bash
git clone https://github.com/Darjona25-code/Folder_Analizer.git
cd Folder_Analizer
pip install -r requirements.txt
python -m api
```

Open `http://localhost:8000` in your browser.

## Building the .exe

```bash
python build.py              # One-folder mode (recommended)
python build.py --onefile    # Single .exe (larger but simpler)
python build.py --clean      # Clean build artifacts first
```

The output will be in `dist/FolderAnalyzer/` (one-folder) or `dist/FolderAnalyzer.exe` (one-file).

### Risk Levels

| Level | Color | Description |
|-------|-------|-------------|
| CRITICAL | Red | System folders (WinSxS, System32, etc.) — **cannot be deleted** |
| CAUTION | Yellow | Program folders (Program Files, etc.) — requires confirmation |
| SAFE | Green | User data, caches, temp files — safe to delete |

## Project Structure

```
Folder_Analizer/
├── api/
│   ├── __init__.py        # Package init
│   ├── __main__.py        # Entry point: python -m api
│   ├── main.py            # FastAPI app, static file mounts
│   ├── models.py          # Pydantic request/response models
│   └── routes.py          # REST API endpoints
├── folder_analyzer/
│   ├── scanner.py         # Multi-threaded disk scanner
│   ├── safety.py          # Risk level detection
│   ├── exporter.py        # JSON/CSV/HTML export
│   ├── i18n.py            # English/Spanish translations
│   └── utils.py           # Helper functions
├── web/
│   ├── index.html         # Main page
│   ├── assets/            # Logo, favicon
│   ├── css/style.css      # Dark theme styles
│   └── js/app.js          # Frontend logic
├── tests/
│   ├── test_api.py        # API endpoint tests
│   ├── test_scanner.py    # Scanner tests
│   ├── test_safety.py     # Safety system tests
│   └── test_i18n.py       # Translation tests
├── build.py               # PyInstaller build script
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Running Tests

```bash
pytest
```

## License

MIT License - see [LICENSE](LICENSE) for details.
