"""Safe deletion module for Folder Analyzer."""

import os
from rich.console import Console
from rich.prompt import Confirm
from send2trash import send2trash

from .scanner import FolderInfo
from .safety import get_risk_level, RiskLevel, is_deletable
from .utils import format_size
from .i18n import I18n


def get_folder_size_recursive(path: str) -> tuple[int, int]:
    total_size = 0
    total_files = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat(follow_symlinks=False).st_size
                    total_files += 1
                elif entry.is_dir(follow_symlinks=False):
                    size, count = get_folder_size_recursive(entry.path)
                    total_size += size
                    total_files += count
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return total_size, total_files


def delete_folders(paths: list[str], i18n: I18n, console: Console) -> int:
    deleted_count = 0
    skipped = []

    for path in paths:
        risk = get_risk_level(path)

        if risk == RiskLevel.CRITICAL:
            console.print(f"[red]{i18n.t('delete_blocked', path=path)}[/red]")
            skipped.append(path)
            continue

        if not os.path.exists(path):
            continue

        size, file_count = get_folder_size_recursive(path)
        console.print(f"\n[yellow]{path}[/yellow] - {format_size(size)}, {file_count:,} files")

        if risk == RiskLevel.CAUTION:
            console.print("[yellow]Warning: This is a program/system folder.[/yellow]")

        if Confirm.ask(i18n.t("delete_confirm")):
            try:
                send2trash(path)
                console.print(f"[green]{i18n.t('delete_success', path=path, size=format_size(size))}[/green]")
                deleted_count += 1
            except Exception as e:
                console.print(f"[red]{i18n.t('delete_failed', path=path, error=str(e))}[/red]")
        else:
            console.print(f"[dim]{i18n.t('delete_cancelled')}[/dim]")

    return deleted_count
