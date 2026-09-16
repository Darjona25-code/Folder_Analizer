; Inno Setup script for Folder Analyzer 3.0.0 (Phase 11).
; Requires the PyInstaller onedir output at dist/FolderAnalyzer
; (paths below are relative to this file's directory).
#define MyAppName "Folder Analyzer"
#define MyAppVersion "3.0.0"
#define MyAppExeName "FolderAnalyzer.exe"

[Setup]
AppId={{7B0E4F2A-3C60-4E1A-9F8B-6D2A81C4E5F3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Darjona25-code
DefaultDirName={localappdata}\Programs\FolderAnalyzer
DefaultGroupName=Folder Analyzer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=FolderAnalyzer-Setup-{#MyAppVersion}
OutputDir=../dist
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "../dist/FolderAnalyzer/*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Folder Analyzer"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Folder Analyzer"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon