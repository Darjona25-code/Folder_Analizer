"""Report exporter for Folder Analyzer - JSON, CSV, HTML.

Phase 6 adds the ``export_*_v2`` variants. They consume the ScanResult already
collected at scan time (``Scanner.scan_result()``) and perform ZERO analysis:
no re-scan, no re-classification, no knowledge-base or classifier access — every
safety value they emit comes from the captured FolderAggregation/Assessment
objects. The v1 ``export_*`` functions are preserved for backward compatibility.
"""

import html
import json
import csv
import os
from datetime import datetime
from typing import Optional

from .scanner import FolderInfo, sort_folders_by_size
from .safety import get_risk_level, get_risk_label
from .utils import format_size
from .i18n import I18n
from .engine.models import Assessment, FolderComposition, ScanResult
from .engine.explain import resolve_reason


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
        writer.writerow([
            i18n.t("col_folder"),
            i18n.t("export_csv_size_bytes"),
            i18n.t("export_csv_size_human"),
            i18n.t("col_files"),
            i18n.t("col_subfolders"),
            i18n.t("col_risk"),
        ])
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
        {i18n.t('files_count', count=f'{root.file_count:,}')} | {i18n.t('folders_count', count=f'{root.folder_count:,}')} |
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
                <th>{i18n.t('col_distribution')}</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Phase 6 — v2 exporters (enriched, annotation-backed, deterministic).
#
# These functions read ONLY the values captured during the scan: the FolderInfo
# tree, the ScanResult perf-folder aggregation and its Assessments. They never
# invoke the knowledge base, classifier, or scanner. Determinism: scan_date is
# injectable, children/rows are canonically sorted, and all dict/field ordering
# is construction-stable, so identical inputs yield byte-identical files.
# ---------------------------------------------------------------------------

_V2_SCHEMA_VERSION = 2


def _assessment_to_dict(assessment: Optional[Assessment]) -> Optional[dict]:
    if assessment is None:
        return None
    return {
        "recommendation": assessment.recommendation.value,
        "confidence": assessment.confidence.value,
        "impact": assessment.impact.value,
        "reason_key": assessment.reason_key,
        "reason_params": assessment.reason_params,
        "detected_category": assessment.detected_category,
        "app_id": assessment.app_id,
        "is_user_data": assessment.is_user_data,
        "is_temporary": assessment.is_temporary,
    }


def _composition_to_dict(composition: Optional[FolderComposition]) -> Optional[dict]:
    if composition is None:
        return None
    return {
        "total_bytes": composition.total_bytes,
        "disposable_bytes": composition.disposable_bytes,
        "user_value_bytes": composition.user_value_bytes,
        "protected_critical_bytes": composition.protected_critical_bytes,
        "known_non_disposable_bytes": composition.known_non_disposable_bytes,
        "unknown_bytes": composition.unknown_bytes,
        "not_resolvable_count": composition.not_resolvable_count,
        "by_category": {
            category: composition.by_category[category]
            for category in sorted(composition.by_category)
        },
    }


def _enrich_node(node: FolderInfo, per_folder: dict) -> dict:
    """Deep-copy a FolderInfo node into the v2 tree shape, enriched with the
    per-folder aggregation captured at scan time. Children are ordered
    canonically by normalized path so identical scan data serializes
    byte-identically regardless of filesystem enumeration order."""
    agg = per_folder.get(os.path.normpath(node.path))
    base = node.to_dict()
    base["analysis_state"] = "analyzed"
    base["files_analyzed"] = agg.files_analyzed if agg is not None else 0
    base["records_retained"] = agg.records_retained if agg is not None else 0
    base["assessment"] = _assessment_to_dict(agg.assessment if agg is not None else None)
    base["composition"] = _composition_to_dict(agg.composition if agg is not None else None)
    base["children"] = [
        _enrich_node(child, per_folder)
        for child in sorted(node.children, key=lambda c: os.path.normpath(c.path))
    ]
    return base


def export_json_v2(
    root: FolderInfo,
    i18n: I18n,
    output_path: str,
    scan_result: ScanResult,
    scan_date: Optional[str] = None,
):
    data = {
        "schema_version": _V2_SCHEMA_VERSION,
        "scan_date": scan_date if scan_date is not None else datetime.now().isoformat(),
        "root_path": root.path,
        "total_size": root.total_size,
        "total_files": root.file_count,
        "total_folders": root.folder_count,
        "files_analyzed": scan_result.files_analyzed,
        "records_retained": scan_result.records_retained,
        "inaccessible_count": scan_result.inaccessible_count,
        "folder_errors": list(scan_result.folder_errors),
    }
    root_agg = scan_result.per_folder.get(os.path.normpath(root.path))
    data["root_assessment"] = _assessment_to_dict(
        root_agg.assessment if root_agg is not None else None
    )
    data["root_composition"] = _composition_to_dict(
        root_agg.composition if root_agg is not None else None
    )
    data["tree"] = _enrich_node(root, scan_result.per_folder)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _iter_descendants(node: FolderInfo):
    for child in node.children:
        yield child
        yield from _iter_descendants(child)


def _top_folder_rows(root: FolderInfo, scan_result: ScanResult, top_n: int) -> list:
    """Descendant rows sorted by (total_size desc, normalized path asc).

    The scan root is never included, mirroring the v1 report: the root is not a
    normal, deletable report row. Sorting is fully deterministic."""
    folders = list(_iter_descendants(root))
    folders.sort(key=lambda f: (-f.total_size, os.path.normpath(f.path)))
    return folders[:top_n]


def export_csv_v2(
    root: FolderInfo,
    i18n: I18n,
    output_path: str,
    scan_result: ScanResult,
    scan_date: Optional[str] = None,
):
    per_folder = scan_result.per_folder
    top = _top_folder_rows(root, scan_result, top_n=500)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            i18n.t("col_folder"),
            i18n.t("export_csv_size_bytes"),
            i18n.t("export_csv_size_human"),
            i18n.t("col_files"),
            i18n.t("col_subfolders"),
            i18n.t("col_risk"),
            i18n.t("col_recommendation"),
            i18n.t("col_confidence"),
            i18n.t("col_impact"),
            i18n.t("col_reason"),
            i18n.t("col_analysis_state"),
            i18n.t("col_files_analyzed"),
            i18n.t("col_records_retained"),
        ])
        for folder in top:
            agg = per_folder.get(os.path.normpath(folder.path))
            risk = get_risk_level(folder.path)
            row = [
                folder.path,
                folder.total_size,
                format_size(folder.total_size),
                folder.file_count,
                folder.folder_count,
                get_risk_label(risk, i18n.lang),
            ]
            if agg is not None and agg.assessment is not None:
                a = agg.assessment
                row += [
                    a.recommendation.value,
                    a.confidence.value,
                    a.impact.value,
                    resolve_reason(a.reason_key, lang=i18n.lang, params=a.reason_params),
                ]
            else:
                row += ["", "", "", ""]
            row += [
                "analyzed",
                agg.files_analyzed if agg is not None else 0,
                agg.records_retained if agg is not None else 0,
            ]
            writer.writerow(row)


def export_html_v2(
    root: FolderInfo,
    i18n: I18n,
    output_path: str,
    scan_result: ScanResult,
    scan_date: Optional[str] = None,
):
    if scan_date is None:
        scan_date = datetime.now().isoformat()
    per_folder = scan_result.per_folder
    top = _top_folder_rows(root, scan_result, top_n=100)
    total = root.total_size

    risk_class = {"CRITICAL": "critical", "CAUTION": "caution", "SAFE": "safe",
                  "CRITICO": "critical", "PRECAUCION": "caution", "SEGURO": "safe"}

    rows_html = ""
    for idx, folder in enumerate(top, 1):
        risk = get_risk_level(folder.path)
        risk_label = get_risk_label(risk, i18n.lang)
        pct = (folder.total_size / total * 100) if total > 0 else 0
        css_class = risk_class.get(risk_label, "safe")

        agg = per_folder.get(os.path.normpath(folder.path))
        if agg is not None and agg.assessment is not None:
            a = agg.assessment
            recommendation = a.recommendation.value
            confidence = a.confidence.value
            impact = a.impact.value
            reason = resolve_reason(a.reason_key, lang=i18n.lang, params=a.reason_params)
        else:
            recommendation = confidence = impact = reason = ""
        analyzed = agg.files_analyzed if agg is not None else 0
        retained = agg.records_retained if agg is not None else 0

        rows_html += f"""
        <tr>
            <td>{idx}</td>
            <td class="path">{html.escape(folder.path)}</td>
            <td class="size">{format_size(folder.total_size)}</td>
            <td>{folder.file_count:,}</td>
            <td>{folder.folder_count:,}</td>
            <td class="{css_class}">{risk_label}</td>
            <td>{html.escape(recommendation)}</td>
            <td>{html.escape(confidence)}</td>
            <td>{html.escape(impact)}</td>
            <td class="reason">{html.escape(reason)}</td>
            <td>{html.escape("analyzed")}</td>
            <td>{analyzed:,}</td>
            <td>{retained:,}</td>
            <td>
                <div class="bar-container">
                    <div class="bar {css_class}" style="width: {pct:.1f}%"></div>
                </div>
                {pct:.1f}%
            </td>
        </tr>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="{i18n.lang}">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(i18n.t('app_title'))} - {html.escape(root.path)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }}
        h1 {{ color: #58a6ff; margin-bottom: 8px; }}
        .meta {{ color: #8b949e; margin-bottom: 24px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
        th {{ background: #21262d; padding: 12px 10px; text-align: left; font-weight: 600; color: #58a6ff; border-bottom: 2px solid #30363d; }}
        td {{ padding: 10px 10px; border-bottom: 1px solid #21262d; }}
        tr:hover {{ background: #1c2128; }}
        .path {{ font-family: 'Cascadia Code', monospace; font-size: 13px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .reason {{ color: #8b949e; max-width: 360px; }}
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
    <h1>{html.escape(i18n.t('app_title'))}</h1>
    <div class="meta">
        {html.escape(i18n.t('treemap_total', size=format_size(total)))} |
        {html.escape(i18n.t('files_count', count=f'{root.file_count:,}'))} | {html.escape(i18n.t('folders_count', count=f'{root.folder_count:,}'))} |
        {html.escape(scan_date)} | {html.escape(i18n.t('col_files_analyzed'))}: {scan_result.files_analyzed:,} | {html.escape(i18n.t('col_records_retained'))}: {scan_result.records_retained:,}
    </div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>{html.escape(i18n.t('col_folder'))}</th>
                <th style="text-align:right">{html.escape(i18n.t('col_size'))}</th>
                <th>{html.escape(i18n.t('col_files'))}</th>
                <th>{html.escape(i18n.t('col_subfolders'))}</th>
                <th>{html.escape(i18n.t('col_risk'))}</th>
                <th>{html.escape(i18n.t('col_recommendation'))}</th>
                <th>{html.escape(i18n.t('col_confidence'))}</th>
                <th>{html.escape(i18n.t('col_impact'))}</th>
                <th>{html.escape(i18n.t('col_reason'))}</th>
                <th>{html.escape(i18n.t('col_analysis_state'))}</th>
                <th>{html.escape(i18n.t('col_files_analyzed'))}</th>
                <th>{html.escape(i18n.t('col_records_retained'))}</th>
                <th>{html.escape(i18n.t('col_distribution'))}</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
