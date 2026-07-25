"""Safety system for Folder Analyzer - detects protected folders and risk levels."""

import os
from enum import Enum


class RiskLevel(Enum):
    CRITICAL = "critical"
    CAUTION = "caution"
    SAFE = "safe"


CRITICAL_FOLDERS = {
    "C:\\Windows\\WinSxS",
    "C:\\Windows\\System32",
    "C:\\Windows\\SysWOW64",
    "C:\\Windows\\Boot",
    "C:\\Windows\\servicing",
    "C:\\Windows\\Installer",
    "C:\\Windows\\WinSxS\\Backup",
    "C:\\ProgramData\\Microsoft\\Windows",
    "C:\\Recovery",
    "C:\\$Recycle.Bin",
    "C:\\System Volume Information",
}

CAUTION_FOLDERS = {
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\Windows",
    "C:\\Users",
}

CAUTION_EXTENSIONS = {
    ".sys", ".dll", ".exe", ".msi", ".cat", ".mum", ".manifest",
}

SYSTEM_SUBPATHS = [
    "\\System32", "\\SysWOW64", "\\WinSxS", "\\Boot", "\\servicing",
    "\\Installer", "\\DriverStore",
]


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
    if "\\APPDATA" in upper or "\\DOWNLOADS" in upper or "\\DOCUMENTS" in upper:
        return False
    if "\\DESKTOP" in upper or "\\PICTURES" in upper or "\\VIDEOS" in upper:
        return False
    if "\\MUSIC" in upper or "\\APPDATA\\LOCAL" in upper:
        return False
    return True


def is_deletable(path: str) -> bool:
    return get_risk_level(path) != RiskLevel.CRITICAL


def get_risk_color(level: RiskLevel) -> str:
    return {
        RiskLevel.CRITICAL: "red",
        RiskLevel.CAUTION: "yellow",
        RiskLevel.SAFE: "green",
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
