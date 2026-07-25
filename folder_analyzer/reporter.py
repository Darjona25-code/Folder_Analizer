"""CLI reporter with Rich tables and tree view for Folder Analyzer."""

from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text

from .scanner import FolderInfo
from .safety import get_risk_level, get_risk_color, get_risk_label, RiskLevel
from .utils import format_size
from .i18n import I18n


def show_top_folders(folders: list[FolderInfo], i18n: I18n, console: Console, top_n: int = 20):
    title = i18n.t("top_folders", n=top_n)
    table = Table(title=title, show_lines=True, title_style="bold cyan")
    table.add_column(i18n.t("col_rank"), style="dim", width=4, justify="right")
    table.add_column(i18n.t("col_folder"), max_width=60)
    table.add_column(i18n.t("col_size"), style="bold", justify="right", width=12)
    table.add_column(i18n.t("col_risk"), justify="center", width=12)
    table.add_column(i18n.t("col_files"), justify="right", width=10)

    for idx, folder in enumerate(folders[:top_n], 1):
        risk = get_risk_level(folder.path)
        risk_label = get_risk_label(risk, i18n.lang)
        risk_color = get_risk_color(risk)

        table.add_row(
            str(idx),
            folder.path,
            format_size(folder.total_size),
            Text(risk_label, style=risk_color),
            f"{folder.file_count:,}",
        )

    console.print(table)


def show_tree(folder: FolderInfo, i18n: I18n, console: Console, max_depth: int = 2):
    tree = _build_tree(folder, i18n, max_depth, 0)
    console.print(tree)


def _build_tree(folder: FolderInfo, i18n: I18n, max_depth: int, current_depth: int) -> Tree:
    risk = get_risk_level(folder.path)
    risk_label = get_risk_label(risk, i18n.lang)
    risk_color = get_risk_color(risk)

    label = Text()
    label.append(f"{folder.name} ", style="bold")
    label.append(f"({format_size(folder.total_size)})", style="cyan")
    label.append(f" [{risk_label}]", style=risk_color)

    tree = Tree(label)

    if current_depth < max_depth:
        sorted_children = sorted(folder.children, key=lambda c: c.total_size, reverse=True)
        for child in sorted_children[:15]:
            child_tree = _build_tree(child, i18n, max_depth, current_depth + 1)
            tree.add(child_tree)

        if len(sorted_children) > 15:
            remaining = len(sorted_children) - 15
            tree.add(Text(f"... +{remaining} more", style="dim"))

    return tree


def show_folder_detail(folder: FolderInfo, i18n: I18n, console: Console):
    console.print(Panel(
        f"{i18n.t('folder_details', path=folder.path)}\n"
        f"{i18n.t('total_size', size=format_size(folder.total_size))}\n"
        f"{i18n.t('total_files', count=f'{folder.file_count:,}')}",
        title=folder.name,
        border_style="cyan",
    ))

    if not folder.children:
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column(i18n.t("col_rank"), width=4, justify="right", style="dim")
    table.add_column(i18n.t("col_folder"), max_width=55)
    table.add_column(i18n.t("col_size"), justify="right", width=12)
    table.add_column(i18n.t("col_risk"), justify="center", width=12)

    sorted_children = sorted(folder.children, key=lambda c: c.total_size, reverse=True)
    for idx, child in enumerate(sorted_children, 1):
        risk = get_risk_level(child.path)
        risk_label = get_risk_label(risk, i18n.lang)
        risk_color = get_risk_color(risk)

        table.add_row(
            str(idx),
            child.name,
            format_size(child.total_size),
            Text(risk_label, style=risk_color),
        )

    console.print(table)
