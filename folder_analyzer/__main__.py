"""Main entry point for Folder Analyzer - interactive CLI menu."""

import argparse
import os
import sys
import locale

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich.text import Text

from .scanner import Scanner, FolderInfo, sort_folders_by_size
from .reporter import show_top_folders, show_tree, show_folder_detail
from .treemap import show_treemap
from .deleter import delete_folders, get_folder_size_recursive
from .exporter import export_json, export_csv, export_html
from .safety import get_risk_level, RiskLevel
from .i18n import I18n
from .utils import format_size, get_default_drive


def detect_language() -> str:
    system_lang = locale.getdefaultlocale()[0] or ""
    if system_lang.startswith("es"):
        return "es"
    return "en"


def choose_language(console: Console) -> str:
    console.print(Panel(
        "[1] English\n[2] Espanol",
        title="Language / Idioma",
        border_style="cyan",
    ))
    choice = Prompt.ask("Select / Selecciona", choices=["1", "2"], default="1")
    return "en" if choice == "1" else "es"


def choose_path(i18n: I18n, console: Console) -> str:
    path = Prompt.ask(i18n.t("scan_path_prompt"), default=get_default_drive())
    path = os.path.normpath(path)
    if not os.path.exists(path):
        console.print(f"[red]Path does not exist: {path}[/red]")
        return choose_path(i18n, console)
    return path


def do_scan(path: str, i18n: I18n, console: Console) -> FolderInfo:
    scanner = Scanner(max_workers=16)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(i18n.t("scanning", path=path), total=None)

        def on_progress(folders, files):
            progress.update(task, description=f"[cyan]{i18n.t('scanning', path=path)}[/cyan] | {folders:,} dirs | {files:,} files")

        result = scanner.scan(path, on_progress=on_progress)
        progress.update(task, completed=True, description=f"[green]{i18n.t('scan_complete')}[/green]")

    console.print(f"[green]{i18n.t('files_scanned', count=f'{scanner.scanned_files:,}')}[/green]")
    console.print(f"[green]{i18n.t('folders_scanned', count=f'{scanner.scanned_folders:,}')}[/green]")
    return result


def get_top_folders(root: FolderInfo) -> list[FolderInfo]:
    return sort_folders_by_size(root, top_n=50)


def show_main_menu(i18n: I18n, console: Console) -> str:
    console.print()
    console.print(Panel(
        f"[1] {i18n.t('menu_details')}\n"
        f"[2] {i18n.t('menu_delete')}\n"
        f"[3] {i18n.t('menu_export')}\n"
        f"[4] {i18n.t('menu_quit')}",
        title=i18n.t("app_title"),
        border_style="cyan",
    ))
    return Prompt.ask(">", choices=["1", "2", "3", "4"])


def action_details(root: FolderInfo, top_folders: list[FolderInfo], i18n: I18n, console: Console):
    show_top_folders(top_folders, i18n, console, top_n=20)
    show_treemap(root, i18n, console)

    while True:
        choice = Prompt.ask(i18n.t("select_folder_num"), default="0")
        if choice == "0":
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(top_folders):
                folder = top_folders[idx]
                show_folder_detail(folder, i18n, console)

                sub_folders = sort_folders_by_size(folder, top_n=15)
                if sub_folders:
                    show_top_folders(sub_folders, i18n, console, top_n=15)
            else:
                console.print(f"[yellow]{i18n.t('enter_number')}[/yellow]")
        except ValueError:
            console.print(f"[yellow]{i18n.t('enter_number')}[/yellow]")


def action_delete(top_folders: list[FolderInfo], i18n: I18n, console: Console):
    show_top_folders(top_folders, i18n, console, top_n=20)

    console.print("\n[yellow]Enter folder numbers to mark for deletion (comma-separated, e.g. 1,3,5):[/yellow]")
    choice = Prompt.ask(">")

    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        console.print(f"[yellow]{i18n.t('enter_number')}[/yellow]")
        return

    selected_paths = []
    for idx in indices:
        if 0 <= idx < len(top_folders):
            folder = top_folders[idx]
            risk = get_risk_level(folder.path)
            size_str = format_size(folder.total_size)

            if risk == RiskLevel.CRITICAL:
                console.print(f"[red]{i18n.t('delete_blocked', path=folder.path)}[/red]")
                continue

            console.print(f"  [cyan]{folder.path}[/cyan] - {size_str}")
            selected_paths.append(folder.path)

    if not selected_paths:
        console.print(f"[yellow]{i18n.t('delete_no_folders')}[/yellow]")
        return

    console.print(f"\n{i18n.t('delete_title')}")
    for p in selected_paths:
        console.print(f"  - {p}")

    deleted = delete_folders(selected_paths, i18n, console)
    console.print(f"\n[green]Deleted {deleted} folder(s).[/green]")


def action_export(root: FolderInfo, i18n: I18n, console: Console):
    console.print(i18n.t("export_title"))
    console.print(f"  {i18n.t('export_json')}")
    console.print(f"  {i18n.t('export_csv')}")
    console.print(f"  {i18n.t('export_html')}")

    choice = Prompt.ask(i18n.t("export_prompt"), choices=["1", "2", "3"])
    filename = Prompt.ask(i18n.t("export_filename"), default="report")

    ext_map = {"1": (".json", export_json), "2": (".csv", export_csv), "3": (".html", export_html)}
    ext, exporter_fn = ext_map[choice]

    output_path = os.path.join(os.getcwd(), f"{filename}{ext}")

    try:
        exporter_fn(root, i18n, output_path)
        console.print(f"[green]{i18n.t('export_success', path=output_path)}[/green]")
    except Exception as e:
        console.print(f"[red]{i18n.t('export_failed', error=str(e))}[/red]")


def main():
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    console = Console(force_terminal=True)

    parser = argparse.ArgumentParser(description="Folder Analyzer - Disk Space Analyzer")
    parser.add_argument("--lang", choices=["en", "es"], help="Language (en/es)")
    parser.add_argument("--path", help="Path to scan")
    args = parser.parse_args()

    if args.lang:
        lang = args.lang
    else:
        lang = choose_language(console)

    i18n = I18n(lang)

    console.print(Panel(
        f"[bold cyan]{i18n.t('app_title')}[/bold cyan]\n"
        f"Scan any drive or folder, view sizes, and safely free disk space.",
        border_style="bright_blue",
    ))

    path = args.path if args.path else choose_path(i18n, console)

    root = do_scan(path, i18n, console)
    top_folders = get_top_folders(root)

    while True:
        choice = show_main_menu(i18n, console)

        if choice == "1":
            action_details(root, top_folders, i18n, console)
        elif choice == "2":
            action_delete(top_folders, i18n, console)
            top_folders = get_top_folders(root)
        elif choice == "3":
            action_export(root, i18n, console)
        elif choice == "4":
            console.print(f"[cyan]{i18n.t('goodbye')}[/cyan]")
            break


if __name__ == "__main__":
    main()
