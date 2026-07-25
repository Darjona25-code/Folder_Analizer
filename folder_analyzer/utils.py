"""Utility functions for Folder Analyzer."""

import os
import string


def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(size_bytes)
    for unit in units:
        if val < 1024:
            return f"{val:.2f} {unit}" if unit != "B" else f"{int(val)} {unit}"
        val /= 1024
    return f"{val:.2f} PB"


def get_drive_roots() -> list[str]:
    roots = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            roots.append(drive)
    return roots


def get_default_drive() -> str:
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            return drive
    return "C:\\"


def safe_path(path: str) -> str:
    return os.path.normpath(path)


def get_parent(path: str) -> str:
    parent = os.path.dirname(path)
    if parent == path:
        return path
    return parent
