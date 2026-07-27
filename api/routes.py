"""API routes for Folder Analyzer v2.0."""

import os
import tempfile
import string

from fastapi import APIRouter, HTTPException
from send2trash import send2trash

from folder_analyzer.scanner import Scanner, sort_folders_by_size
from folder_analyzer.safety import (
    get_risk_level, get_risk_color, get_risk_hex, get_risk_label, is_deletable, RiskLevel
)
from folder_analyzer.utils import format_size
from folder_analyzer.exporter import export_json, export_csv, export_html
from folder_analyzer.i18n import I18n

from .models import (
    ScanRequest, ScanResponse, ScanStats, FolderDict, FolderDetailResponse,
    DeleteRequest, DeleteResponse, DeleteResult,
    ExportRequest, DiskInfo,
)

router = APIRouter()

_last_scan_root = None


def _find_folder_by_path(folder, target_path: str):
    """Recursively find a FolderInfo node by path in the scan tree."""
    normalized_target = os.path.normpath(target_path).upper()
    normalized_current = os.path.normpath(folder.path).upper()

    if normalized_current == normalized_target:
        return folder

    for child in folder.children:
        result = _find_folder_by_path(child, target_path)
        if result is not None:
            return result

    return None


def _folder_to_dict(folder) -> FolderDict:
    risk = get_risk_level(folder.path)
    return FolderDict(
        path=folder.path,
        name=folder.name,
        total_size=folder.total_size,
        file_count=folder.file_count,
        folder_count=folder.folder_count,
        direct_size=folder.direct_size,
        children=[_folder_to_dict(c) for c in folder.children],
        error=folder.error,
        risk=risk.value,
        risk_color=get_risk_hex(risk),
        deletable=is_deletable(folder.path),
    )


@router.post("/api/scan", response_model=ScanResponse)
def scan_folder(req: ScanRequest):
    global _last_scan_root

    path = os.path.normpath(req.path)
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")

    scanner = Scanner(max_workers=16)
    root = scanner.scan(path)
    _last_scan_root = root

    top_folders_raw = sort_folders_by_size(root, top_n=50)
    top_folders = [_folder_to_dict(f) for f in top_folders_raw]

    stats = ScanStats(
        total_size=root.total_size,
        total_files=root.file_count,
        total_folders=root.folder_count,
        scan_path=path,
    )

    return ScanResponse(
        root=_folder_to_dict(root),
        stats=stats,
        top_folders=top_folders,
    )


@router.get("/api/folders")
def get_folders(limit: int = 50):
    global _last_scan_root
    if _last_scan_root is None:
        raise HTTPException(status_code=400, detail="No scan performed yet. POST /api/scan first.")

    top = sort_folders_by_size(_last_scan_root, top_n=limit)
    return [_folder_to_dict(f) for f in top]


@router.get("/api/folder/detail", response_model=FolderDetailResponse)
def get_folder_detail(path: str):
    global _last_scan_root
    if _last_scan_root is None:
        raise HTTPException(status_code=400, detail="No scan performed yet. POST /api/scan first.")

    folder = _find_folder_by_path(_last_scan_root, path)
    if folder is None:
        raise HTTPException(status_code=404, detail=f"Folder not found in scan tree: {path}")

    children = [_folder_to_dict(c) for c in folder.children]

    safe_count = sum(1 for c in children if c.risk == "safe")
    caution_count = sum(1 for c in children if c.risk == "caution")
    critical_count = sum(1 for c in children if c.risk == "critical")

    return FolderDetailResponse(
        folder=_folder_to_dict(folder),
        children=children,
        safe_count=safe_count,
        caution_count=caution_count,
        critical_count=critical_count,
    )


@router.post("/api/delete", response_model=DeleteResponse)
def delete_folders(req: DeleteRequest):
    deleted = []
    blocked = []

    for path in req.paths:
        norm = os.path.normpath(path)
        risk = get_risk_level(norm)

        if risk == RiskLevel.CRITICAL:
            blocked.append(norm)
            continue

        if not os.path.exists(norm):
            deleted.append(DeleteResult(path=norm, success=False, error="Path does not exist"))
            continue

        try:
            send2trash(norm)
            deleted.append(DeleteResult(path=norm, success=True))
        except Exception as e:
            deleted.append(DeleteResult(path=norm, success=False, error=str(e)))

    return DeleteResponse(
        deleted=deleted,
        blocked=blocked,
        total_deleted=sum(1 for d in deleted if d.success),
        total_blocked=len(blocked),
    )


@router.post("/api/export")
def export_report(req: ExportRequest):
    global _last_scan_root
    if _last_scan_root is None:
        raise HTTPException(status_code=400, detail="No scan performed yet. POST /api/scan first.")

    i18n = I18n("en")

    with tempfile.TemporaryDirectory() as tmpdir:
        ext_map = {
            "json": (".json", export_json),
            "csv": (".csv", export_csv),
            "html": (".html", export_html),
        }

        if req.format not in ext_map:
            raise HTTPException(status_code=400, detail=f"Invalid format: {req.format}. Use json, csv, or html.")

        ext, exporter_fn = ext_map[req.format]
        output_path = os.path.join(tmpdir, f"report{ext}")
        exporter_fn(_last_scan_root, i18n, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

    media_types = {
        "json": "application/json",
        "csv": "text/csv",
        "html": "text/html",
    }

    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=media_types[req.format],
        headers={"Content-Disposition": f"attachment; filename=report{ext}"},
    )


@router.get("/api/drives")
def get_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            try:
                import psutil
                usage = psutil.disk_usage(drive_path)
                drives.append(DiskInfo(
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent,
                ))
            except Exception:
                drives.append(DiskInfo(total=0, used=0, free=0, percent=0))
    return drives


@router.get("/api/stats")
def get_stats():
    global _last_scan_root
    if _last_scan_root is None:
        raise HTTPException(status_code=400, detail="No scan performed yet.")

    return ScanStats(
        total_size=_last_scan_root.total_size,
        total_files=_last_scan_root.file_count,
        total_folders=_last_scan_root.folder_count,
        scan_path=_last_scan_root.path,
    )
