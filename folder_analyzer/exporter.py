"""Report exporter for Folder Analyzer - JSON, CSV, HTML."""

import json
import csv
import os
from datetime import datetime

from .scanner import FolderInfo, sort_folders_by_size
from .safety import get_risk_level, get_risk_label
from .utils import format_size
from .i18n import I18n


def export_json(root: FolderInfo, i18n: I18n, output_path: str):
    data = {
        "scan_date": datetime.now().isoformat(),
        "root_path": root.path,
        "total_size": root.total_size,
        "total_files": root.file_count,
        "total_folders": root.folder_count,
        "tree": root.to_dict(),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_csv(root: FolderInfo, i18n: I18n, output_path: str):
    top_folders = sort_folders_by_size(root, top_n=500)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Folder", "Size (bytes)", "Size (human)", "Files", "Subfolders", "Risk"])
        for folder in top_folders:
            risk = get_risk_level(folder.path)
            writer.writerow([
                folder.path,
                folder.total_size,
                format_size(folder.total_size),
                folder.file_count,
                folder.folder_count,
                get_risk_label(risk, i18n.lang),
            ])


def export_html(root: FolderInfo, i18n: I18n, output_path: str):
    top_folders = sort_folders_by_size(root, top_n=100)
    total = root.total_size

    rows_html = ""
    for idx, folder in enumerate(top_folders, 1):
        risk = get_risk_level(folder.path)
        risk_label = get_risk_label(risk, i18n.lang)
        pct = (folder.total_size / total * 100) if total > 0 else 0

        risk_class = {"CRITICAL": "critical", "CAUTION": "caution", "SAFE": "safe",
                      "CRITICO": "critical", "PRECAUCION": "caution", "SEGURO": "safe"}
        css_class = risk_class.get(risk_label, "safe")

        rows_html += f"""
        <tr>
            <td>{idx}</td>
            <td class="path">{folder.path}</td>
            <td class="size">{format_size(folder.total_size)}</td>
            <td>{folder.file_count:,}</td>
            <td class="{css_class}">{risk_label}</td>
            <td>
                <div class="bar-container">
                    <div class="bar {css_class}" style="width: {pct:.1f}%"></div>
                </div>
                {pct:.1f}%
            </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="{i18n.lang}">
<head>
    <meta charset="UTF-8">
    <title>{i18n.t('app_title')} - {root.path}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }}
        h1 {{ color: #58a6ff; margin-bottom: 8px; }}
        .meta {{ color: #8b949e; margin-bottom: 24px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
        th {{ background: #21262d; padding: 12px 16px; text-align: left; font-weight: 600; color: #58a6ff; border-bottom: 2px solid #30363d; }}
        td {{ padding: 10px 16px; border-bottom: 1px solid #21262d; }}
        tr:hover {{ background: #1c2128; }}
        .path {{ font-family: 'Cascadia Code', monospace; font-size: 13px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .size {{ font-weight: bold; color: #58a6ff; text-align: right; }}
        .critical {{ color: #f85149; font-weight: bold; }}
        .caution {{ color: #d29922; font-weight: bold; }}
        .safe {{ color: #3fb950; font-weight: bold; }}
        .bar-container {{ width: 120px; height: 12px; background: #21262d; border-radius: 6px; display: inline-block; vertical-align: middle; margin-right: 8px; }}
        .bar {{ height: 100%; border-radius: 6px; }}
        .bar.critical {{ background: #f85149; }}
        .bar.caution {{ background: #d29922; }}
        .bar.safe {{ background: #3fb950; }}
    </style>
</head>
<body>
    <h1>{i18n.t('app_title')}</h1>
    <div class="meta">
        {i18n.t('treemap_total', size=format_size(total))} |
        {root.file_count:,} files | {root.folder_count:,} folders |
        {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>{i18n.t('col_folder')}</th>
                <th style="text-align:right">{i18n.t('col_size')}</th>
                <th>{i18n.t('col_files')}</th>
                <th>{i18n.t('col_risk')}</th>
                <th>Distribution</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
