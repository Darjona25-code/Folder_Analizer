"""Safe deletion module for Folder Analyzer."""

import os

from rich.console import Console
from rich.prompt import Confirm
from send2trash import send2trash

from .safety import get_risk_level, RiskLevel
from .utils import format_size
from .i18n import I18n


def get_folder_size(path: str) -> tuple[int, int]:
    """Compute the total size and file count below *path*.

    Uses an explicit stack instead of recursion to avoid Python's recursion
    limit on deep directory trees.
    """
    total_size = 0
    total_files = 0
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except (PermissionError, OSError):
            continue

        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat(follow_symlinks=False).st_size
                    total_files += 1
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
            except (PermissionError, OSError):
                continue

    return total_size, total_files


# Backwards-compatible alias of the previous recursive implementation name.
get_folder_size_recursive = get_folder_size


def is_protected_path(path: str, protected_roots: list[str]) -> bool:
    """Return True if *path* equals a protected root or is an ancestor of one.

    This prevents the currently scanned root (or any of its parents) from
    being sent to the Recycle Bin as a side effect of deleting a sibling.
    """
    norm = os.path.normpath(path).upper()
    for root in protected_roots:
        root_norm = os.path.normpath(root).upper()
        if norm == root_norm:
            return True
        if root_norm.startswith(norm + os.sep):
            return True
    return False


def delete_folders(
    paths: list[str],
    i18n: I18n,
    console: Console,
    stats: dict[str, tuple[int, int]] | None = None,
    protected: list[str] | None = None,
) -> int:
    """Send *paths* to the Recycle Bin with safety checks.

    Args:
        stats: Optional mapping of path -> (total_size, file_count) captured
            during the scan. When provided, avoids re-scanning the folder.
        protected: Optional list of roots that must not be deleted (or whose
            ancestors must not be deleted).
    """
    deleted_count = 0
    protected = protected or []

    for path in paths:
        risk = get_risk_level(path)

        if risk == RiskLevel.CRITICAL:
            console.print(f"[red]{i18n.t('delete_blocked', path=path)}[/red]")
            continue

        if is_protected_path(path, protected):
            console.print(f"[red]{i18n.t('delete_root_blocked', path=path)}[/red]")
            continue

        if not os.path.exists(path):
            continue

        if stats and path in stats:
            size, file_count = stats[path]
        else:
            size, file_count = get_folder_size(path)

        console.print(f"\n[yellow]{path}[/yellow] - {format_size(size)}, {file_count:,} files")

        if risk == RiskLevel.CAUTION:
            console.print(f"[yellow]{i18n.t('delete_warning_program')}[/yellow]")

        confirmed = True
        try:
            confirmed = Confirm.ask(i18n.t("delete_confirm"))
        except EOFError:
            confirmed = False

        if confirmed:
            try:
                send2trash(path)
                console.print(f"[green]{i18n.t('delete_success', path=path, size=format_size(size))}[/green]")
                deleted_count += 1
            except Exception as e:
                console.print(f"[red]{i18n.t('delete_failed', path=path, error=str(e))}[/red]")
        else:
            console.print(f"[dim]{i18n.t('delete_cancelled')}[/dim]")

    return deleted_count