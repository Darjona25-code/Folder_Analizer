"""Safe deletion module for Folder Analyzer."""

import os

from rich.console import Console
from rich.prompt import Confirm
from send2trash import send2trash

from .audit import DeletionAuditor
from .safety import get_risk_level, RiskLevel
from .security_guard import (
    GuardStatus,
    display_path,
    is_protected_path,
    validate_delete_target,
    revalidate,
)
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

# Backwards-compatible re-export: existing callers import this from deleter.
__all__ = [
    "get_folder_size",
    "get_folder_size_recursive",
    "is_protected_path",
    "delete_folders",
]


def delete_folders(
    paths: list[str],
    i18n: I18n,
    console: Console,
    stats: dict[str, tuple[int, int]] | None = None,
    protected: list[str] | None = None,
    scan_root: str | None = None,
    audit_log: str | None = None,
) -> int:
    """Send *paths* to the Recycle Bin with safety checks.

    Every path passes the six-condition deletion guard, is re-validated
    immediately before send2trash, and is recorded in the audit log.

    Args:
        stats: Optional mapping of path -> (total_size, file_count) captured
            during the scan. When provided, avoids re-scanning the folder.
        protected: Optional list of roots that must not be deleted (or whose
            ancestors must not be deleted).
        scan_root: Optional scanned root; enforces canonical containment.
        audit_log: Optional path of the append-only JSONL audit log.
    """
    deleted_count = 0
    protected = protected or []
    auditor = DeletionAuditor(audit_log) if audit_log else None

    def _audit(verdict, status: str, success: bool | None = None):
        if auditor is None:
            return
        error = verdict.reason if verdict else ""
        auditor.record(
            status=status,
            original=display_path(verdict.original) if verdict else "",
            canonical=verdict.canonical if verdict else None,
            reason=error,
            success=success,
            risk=getattr(get_risk_level(verdict.original), "value", None)
            if verdict else None,
        )

    for path in paths:
        verdict = validate_delete_target(path, scan_root=scan_root, protected_roots=protected)
        original = display_path(path)

        if verdict.status == GuardStatus.INVALID_INPUT:
            _audit(verdict, "denied", success=False)
            console.print(f"[red]{i18n.t('delete_unresolvable', path=original, reason=verdict.reason)}[/red]")
            continue

        if verdict.status == GuardStatus.NOT_FOUND:
            _audit(verdict, "failure", success=False)
            console.print(f"[yellow]{i18n.t('delete_missing', path=original)}[/yellow]")
            continue

        if verdict.status == GuardStatus.NOT_RESOLVABLE:
            _audit(verdict, "deferred", success=False)
            console.print(f"[red]{i18n.t('delete_unresolvable', path=original, reason=verdict.reason)}[/red]")
            continue

        if verdict.status == GuardStatus.DENIED_ROOT or verdict.status == GuardStatus.DENIED_PROTECTED:
            _audit(verdict, "denied", success=False)
            console.print(f"[red]{i18n.t('delete_root_blocked', path=original)}[/red]")
            continue

        if verdict.status == GuardStatus.DENIED_CONTAINMENT:
            _audit(verdict, "denied", success=False)
            console.print(f"[red]{i18n.t('delete_blocked_containment', path=original)}[/red]")
            continue

        if verdict.status == GuardStatus.DENIED_CRITICAL:
            _audit(verdict, "denied", success=False)
            console.print(f"[red]{i18n.t('delete_blocked', path=original)}[/red]")
            continue

        risk = get_risk_level(path)

        if stats and path in stats:
            size, file_count = stats[path]
        else:
            size, file_count = get_folder_size(path)

        console.print(f"\n[yellow]{original}[/yellow] - {format_size(size)}, {file_count:,} files")

        if risk == RiskLevel.CAUTION:
            console.print(f"[yellow]{i18n.t('delete_warning_program')}[/yellow]")

        confirmed = True
        try:
            confirmed = Confirm.ask(i18n.t("delete_confirm"))
        except EOFError:
            confirmed = False

        if not confirmed:
            console.print(f"[dim]{i18n.t('delete_cancelled')}[/dim]")
            continue

        # Condition 6: final revalidation immediately before deletion.
        final = revalidate(path, scan_root=scan_root, protected_roots=protected)
        if not final.ok:
            _audit(final, "denied", success=False)
            console.print(f"[red]{i18n.t('delete_unresolvable', path=original, reason=final.reason)}[/red]")
            continue

        try:
            send2trash(path)
            _audit(final, "success", success=True)
            console.print(f"[green]{i18n.t('delete_success', path=original, size=format_size(size))}[/green]")
            deleted_count += 1
        except Exception as e:
            _audit(final, "failure", success=False)
            console.print(f"[red]{i18n.t('delete_failed', path=original, error=str(e))}[/red]")

    return deleted_count