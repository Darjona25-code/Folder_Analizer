# Folder Analyzer

A Python CLI tool that scans any drive or folder, reports disk usage, and safely frees disk space by sending files to the Recycle Bin.

## Features

- **Fast multi-threaded scanning** — Uses `ThreadPoolExecutor` to scan drives quickly
- **Interactive CLI** — Rich terminal UI with tables, trees, and progress bars
- **ASCII treemap** — Visual bar chart showing disk usage proportions
- **Safety system** — Color-coded risk levels (CRITICAL / CAUTION / SAFE) to protect system folders
- **Safe deletion** — Sends files to Recycle Bin (recoverable) instead of permanent delete
- **Export reports** — Save scan results as JSON, CSV, or a visual HTML report
- **Bilingual** — Full English and Spanish support (`--lang en` / `--lang es`)

## Installation

```bash
git clone https://github.com/Darjona25-code/Folder_Analizer.git
cd Folder_Analizer
pip install -r requirements.txt
```

## Usage

```bash
# Interactive mode
python -m folder_analyzer

# Specify language and path
python -m folder_analyzer --lang es --path C:\

# Quick scan with arguments
python -m folder_analyzer --lang en --path D:\Games
```

### Menu Options

| Option | Description |
|--------|-------------|
| **1 - View Details** | Drill into folders, see subfolder sizes and risk levels |
| **2 - Delete** | Mark folders for safe deletion to Recycle Bin |
| **3 - Export** | Export report as JSON, CSV, or self-contained HTML |
| **4 - Quit** | Exit the application |

### Risk Levels

| Level | Color | Description |
|-------|-------|-------------|
| CRITICAL | Red | System folders (WinSxS, System32, etc.) — **cannot be deleted** |
| CAUTION | Yellow | Program folders (Program Files, etc.) — requires confirmation |
| SAFE | Green | User data, caches, temp files — safe to delete |

## Project Structure

```
Folder_Analizer/
├── folder_analyzer/
│   ├── __init__.py        # Package version
│   ├── __main__.py        # Entry point + interactive menu
│   ├── scanner.py         # Multi-threaded disk scanner
│   ├── reporter.py        # Rich tables and tree view
│   ├── treemap.py         # ASCII treemap visualization
│   ├── deleter.py         # Safe deletion via Recycle Bin
│   ├── safety.py          # Risk level detection
│   ├── exporter.py        # JSON/CSV/HTML export
│   ├── i18n.py            # English/Spanish translations
│   └── utils.py           # Helper functions
├── tests/
│   ├── test_scanner.py
│   ├── test_safety.py
│   └── test_i18n.py
├── requirements.txt
├── pyproject.toml
├── LICENSE                # MIT
└── README.md
```

## Dependencies

- [Rich](https://github.com/Textualize/rich) — Terminal UI (tables, trees, progress bars)
- [send2trash](https://github.com/thesophist/send2trash) — Cross-platform Recycle Bin support
- [psutil](https://github.com/giampaolo/psutil) — System/disk utilities
- [colorama](https://github.com/tartley/colorama) — Cross-platform terminal colors

## Running Tests

```bash
pip install pytest
pytest tests/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
