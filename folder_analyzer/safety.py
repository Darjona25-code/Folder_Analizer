"""Safety system for Folder Analyzer - detects protected folders and risk levels."""

import os
from enum import Enum


class RiskLevel(Enum):
    CRITICAL = "critical"
    CAUTION = "caution"
    SAFE = "safe"


CRITICAL_FOLDERS = {
    "C:\\Windows",
    "C:\\Windows\\WinSxS",
    "C:\\Windows\\System32",
    "C:\\Windows\\SysWOW64",
    "C:\\Windows\\Boot",
    "C:\\Windows\\servicing",
    "C:\\Windows\\Installer",
    "C:\\Windows\\WinSxS\\Backup",
    "C:\\Windows\\Fonts",
    "C:\\Windows\\System",
    "C:\\Windows\\System Resources",
    "C:\\Windows\\INF",
    "C:\\Windows\\Registration",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\Program Files\\Common Files",
    "C:\\Program Files\\Internet Explorer",
    "C:\\Program Files\\Windows Defender",
    "C:\\Program Files\\Windows Mail",
    "C:\\Program Files\\Windows Media Player",
    "C:\\Program Files\\Windows NT",
    "C:\\Program Files\\Windows Photo Viewer",
    "C:\\Program Files\\Windows Portable Devices",
    "C:\\Program Files\\Windows Sidebar",
    "C:\\Program Files\\WindowsPowerShell",
    "C:\\Program Files (x86)\\Common Files",
    "C:\\ProgramData\\Microsoft\\Windows",
    "C:\\ProgramData\\Microsoft\\Windows\\Start Menu",
    "C:\\Recovery",
    "C:\\$Recycle.Bin",
    "C:\\System Volume Information",
    "C:\\pagefile.sys",
    "C:\\swapfile.sys",
    "C:\\hiberfil.sys",
}

CAUTION_FOLDERS = {
    "C:\\ProgramData",
    "C:\\Users",
}

CAUTION_EXTENSIONS = {
    ".sys", ".dll", ".exe", ".msi", ".cat", ".mum", ".manifest",
}

SYSTEM_SUBPATHS = [
    "\\System32", "\\SysWOW64", "\\WinSxS", "\\Boot", "\\servicing",
    "\\Installer", "\\DriverStore", "\\Fonts", "\\INF",
    "\\Registration", "\\System", "\\System Resources",
]

PROTECTED_DRIVES = {"C:"}


def get_risk_level(path: str) -> RiskLevel:
    normalized = os.path.normpath(path).upper()

    for crit in CRITICAL_FOLDERS:
        if normalized == crit.upper():
            return RiskLevel.CRITICAL

    for crit in CRITICAL_FOLDERS:
        if normalized.startswith(crit.upper()):
            return RiskLevel.CRITICAL

    for subpath in SYSTEM_SUBPATHS:
        if f"\\WINDOWS{subpath.upper()}" in normalized:
            return RiskLevel.CRITICAL

    for cau in CAUTION_FOLDERS:
        if normalized == cau.upper():
            return RiskLevel.CAUTION

    for cau in CAUTION_FOLDERS:
        if normalized.startswith(cau.upper() + "\\"):
            if _is_program_folder(normalized):
                return RiskLevel.CAUTION

    return RiskLevel.SAFE


def _is_program_folder(path: str) -> bool:
    upper = path.upper()
    # AppData\Roaming holds sensitive per-user application data -> treat as CAUTION.
    if "\\APPDATA\\ROAMING" in upper:
        return True
    if "\\APPDATA" in upper or "\\DOWNLOADS" in upper or "\\DOCUMENTS" in upper:
        return False
    if "\\DESKTOP" in upper or "\\PICTURES" in upper or "\\VIDEOS" in upper:
        return False
    if "\\MUSIC" in upper or "\\DESKTOP\\FOLDERS" in upper or "\\MY DOCUMENTS" in upper:
        return False
    return True


def is_deletable(path: str) -> bool:
    return get_risk_level(path) != RiskLevel.CRITICAL


def is_protected(path: str) -> bool:
    return get_risk_level(path) in (RiskLevel.CRITICAL, RiskLevel.CAUTION)


def get_risk_color(level: RiskLevel) -> str:
    return {
        RiskLevel.CRITICAL: "red",
        RiskLevel.CAUTION: "yellow",
        RiskLevel.SAFE: "green",
    }[level]


def get_risk_hex(level: RiskLevel) -> str:
    return {
        RiskLevel.CRITICAL: "#f85149",
        RiskLevel.CAUTION: "#d29922",
        RiskLevel.SAFE: "#3fb950",
    }[level]


def get_risk_label(level: RiskLevel, lang: str = "en") -> str:
    labels = {
        "en": {
            RiskLevel.CRITICAL: "CRITICAL",
            RiskLevel.CAUTION: "CAUTION",
            RiskLevel.SAFE: "SAFE",
        },
        "es": {
            RiskLevel.CRITICAL: "CRITICO",
            RiskLevel.CAUTION: "PRECAUCION",
            RiskLevel.SAFE: "SEGURO",
        },
    }
    return labels.get(lang, labels["en"])[level]
