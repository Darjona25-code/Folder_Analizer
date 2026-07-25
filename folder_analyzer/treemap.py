"""ASCII treemap visualization for Folder Analyzer."""

from rich.console import Console
from rich.text import Text

from .scanner import FolderInfo
from .safety import get_risk_level, get_risk_color, RiskLevel
from .utils import format_size
from .i18n import I18n


BAR_FULL = "#"
BAR_PART = "="
BAR_WIDTH = 40


def show_treemap(root: FolderInfo, i18n: I18n, console: Console, top_n: int = 15):
    title = i18n.t("treemap_title")
    total = root.total_size

    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print(f"[dim]{i18n.t('treemap_total', size=format_size(total))}[/dim]\n")

    sorted_children = sorted(root.children, key=lambda c: c.total_size, reverse=True)
    display_folders = sorted_children[:top_n]

    if not display_folders:
        return

    max_size = max(f.total_size for f in display_folders)

    for folder in display_folders:
        risk = get_risk_level(folder.path)
        color = get_risk_color(risk)
        pct = (folder.total_size / total * 100) if total > 0 else 0
        bar_len = int((folder.total_size / max_size) * BAR_WIDTH) if max_size > 0 else 0

        if folder.total_size == 0:
            continue

        bar = BAR_FULL * max(bar_len, 1)
        name = folder.name if len(folder.name) <= 30 else folder.name[:27] + "..."

        line = Text()
        line.append(f"  {bar} ", style=color)
        line.append(f"{name}", style="bold")
        line.append(f" {format_size(folder.total_size)}", style="cyan")
        line.append(f" ({pct:.1f}%)", style="dim")

        console.print(line)

    if len(sorted_children) > top_n:
        remaining_size = sum(f.total_size for f in sorted_children[top_n:])
        remaining_count = len(sorted_children) - top_n
        pct = (remaining_size / total * 100) if total > 0 else 0
        console.print(f"  [dim]... +{remaining_count} other folders ({format_size(remaining_size)}, {pct:.1f}%)[/dim]")

    console.print()
