"""PyInstaller build script for Folder Analyzer v3.0.

Usage:
    python build.py              # Build .exe (one-folder mode)
    python build.py --onefile    # Build single .exe (one-file mode)
    python build.py --clean      # Clean build artifacts first
"""

import subprocess
import sys
import shutil
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
ASSETS_DIR = WEB_DIR / "assets"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ICON = ASSETS_DIR / "favicon.ico"
ENTRY = ROOT / "api" / "__main__.py"


def clean():
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed {d}")
    for f in ROOT.glob("*.spec"):
        f.unlink()
        print(f"  Removed {f}")


def build(onefile: bool = False):
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "FolderAnalyzer",
        "--console",
        f"--icon={ICON}",
        f"--add-data={WEB_DIR};web",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--noconfirm",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    cmd.append(str(ENTRY))

    print(f"Building FolderAnalyzer ({'one-file' if onefile else 'one-folder'} mode)...")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        if onefile:
            exe = DIST_DIR / "FolderAnalyzer.exe"
            print(f"\nBuild successful: {exe}")
        else:
            exe = DIST_DIR / "FolderAnalyzer" / "FolderAnalyzer.exe"
            print(f"\nBuild successful: {exe}")
    else:
        print("\nBuild failed.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Build Folder Analyzer .exe")
    parser.add_argument("--onefile", action="store_true", help="Single .exe (larger but simpler)")
    parser.add_argument("--clean", action="store_true", help="Remove build artifacts first")
    args = parser.parse_args()

    if args.clean:
        print("Cleaning build artifacts...")
        clean()

    build(onefile=args.onefile)


if __name__ == "__main__":
    main()
