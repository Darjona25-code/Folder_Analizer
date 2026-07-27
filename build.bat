@echo off
echo ================================
echo  Folder Analyzer - Build Script
echo  Caza Bytes
echo ================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo Installing build dependencies...
python -m pip install --quiet pyinstaller>=6.0

echo.
echo Building FolderAnalyzer.exe ...
python "%~dp0build.py" %*

echo.
echo Done!
pause
