# Phase 11 build: PyInstaller onedir bundle + Inno Setup installer.
# Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File packaging/build_desktop.ps1
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ISCC = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

Write-Host "== PyInstaller onedir build =="
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\FolderAnalyzer.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path -LiteralPath $ISCC)) {
    throw "ISCC not found at ${ISCC} - install Inno Setup 6 first."
}

Write-Host "== Inno Setup installer build =="
& $ISCC "packaging\folder-analyzer.iss"
exit $LASTEXITCODE