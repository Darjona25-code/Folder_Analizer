"""API routes for Folder Analyzer v2.0."""

import os
import string

from fastapi import APIRouter, HTTPException, Request
from send2trash import send2trash

from folder_analyzer.scanner import Scanner, sort_folders_by_size
from folder_analyzer.safety import (
    get_risk_level,
    get_risk_hex,
    is_deletable,
)
from folder_analyzer.audit import DeletionAuditor
from folder_analyzer.security_guard import (
    GuardStatus,
    display_path,
    is_protected_path,
    validate_delete_target,
    revalidate,
)
from folder_analyzer.exporter import export_json_v2, export_csv_v2, export_html_v2
from folder_analyzer.i18n import I18n

from .models import (
    ScanRequest, ScanResponse, ScanStats, FolderDict,
    DeleteRequest, DeleteResponse, DeleteResult,
    ExportRequest, DiskInfo,
)

router = APIRouter()

_EXPORT_MEDIA_TYPES = {
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "html": "text/html; charset=utf-8",
}


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


def _get_last_scan_root(request: Request):
    """Return the most recent scan root stored on the app, or raise 400.

    The scan state lives on ``app.state`` so it is explicit, per-process, and
    resets predictably when the server restarts or reloads.
    """
    root = getattr(request.app.state, "last_scan_root", None)
    if root is None:
        raise HTTPException(status_code=400, detail="No scan performed yet. POST /api/scan first.")
    return root


@router.post("/api/scan", response_model=ScanResponse)
def scan_folder(req: ScanRequest, request: Request):
    path = os.path.normpath(req.path)
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")

    scanner = Scanner(max_workers=16)
    root = scanner.scan(path)
    request.app.state.last_scan_root = root
    request.app.state.last_scan_result = scanner.scan_result()

    root_dict = _folder_to_dict(root)
    # The scanned root is never a normal deletable item.
    root_dict.deletable = False

    top_folders_raw = sort_folders_by_size(root, top_n=50)
    top_folders = [_folder_to_dict(f) for f in top_folders_raw]

    stats = ScanStats(
        total_size=root.total_size,
        total_files=root.file_count,
        total_folders=root.folder_count,
        scan_path=path,
    )

    return ScanResponse(
        root=root_dict,
        stats=stats,
        top_folders=top_folders,
    )


@router.get("/api/folders")
def get_folders(request: Request, limit: int = 50):
    root = _get_last_scan_root(request)
    top = sort_folders_by_size(root, top_n=limit)
    return [_folder_to_dict(f) for f in top]


@router.post("/api/delete", response_model=DeleteResponse)
def delete_folders(req: DeleteRequest, request: Request):
    deleted = []
    blocked = []
    root = getattr(request.app.state, "last_scan_root", None)
    scan_root = getattr(root, "path", None) if root else None
    protected = [scan_root] if scan_root else []
    auditor = DeletionAuditor()

    for path in req.paths:
        original = display_path(path)
        verdict = validate_delete_target(path, scan_root=scan_root, protected_roots=protected)

        if verdict.status == GuardStatus.INVALID_INPUT:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "INVALID_PATH",
                    "message": "Invalid path input",
                    "path": original,
                },
            )

        if verdict.status == GuardStatus.NOT_RESOLVABLE:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "UNRESOLVABLE_PATH",
                    "message": verdict.reason,
                    "path": original,
                },
            )

        if verdict.status == GuardStatus.NOT_FOUND:
            auditor.record(status="failure", original=original,
                           canonical=verdict.canonical, reason=verdict.reason, success=False)
            deleted.append(DeleteResult(
                path=original, success=False, error="Path does not exist",
                status="failure", reason=verdict.reason,
            ))
            continue

        if verdict.denied:
            auditor.record(status="denied", original=original,
                           canonical=verdict.canonical, reason=verdict.reason, success=False)
            blocked.append(original)
            continue

        # Condition 6: final revalidation immediately before deletion.
        final = revalidate(path, scan_root=scan_root, protected_roots=protected)
        if not final.ok:
            auditor.record(status="denied", original=original,
                           canonical=verdict.canonical, reason=final.reason, success=False)
            blocked.append(original)
            continue

        try:
            send2trash(path)
            auditor.record(status="success", original=original,
                           canonical=verdict.canonical, reason=verdict.reason, success=True)
            deleted.append(DeleteResult(path=original, success=True, status="success"))
        except Exception as e:
            auditor.record(status="failure", original=original,
                           canonical=verdict.canonical, reason=str(e), success=False)
            deleted.append(DeleteResult(path=original, success=False, error=str(e), status="failure"))

    return DeleteResponse(
        deleted=deleted,
        blocked=blocked,
        total_deleted=sum(1 for d in deleted if d.success),
        total_blocked=len(blocked),
    )


@router.post("/api/export")
def export_report(req: ExportRequest, request: Request):
    root = _get_last_scan_root(request)
    scan_result = getattr(request.app.state, "last_scan_result", None)
    if scan_result is None:
        raise HTTPException(status_code=400, detail="No scan analysis available. POST /api/scan first.")

    lang = req.lang if req.lang in ("en", "es") else "en"
    i18n = I18n(lang)

    ext_map = {
        "json": (".json", export_json_v2),
        "csv": (".csv", export_csv_v2),
        "html": (".html", export_html_v2),
    }

    if req.format not in ext_map:
        raise HTTPException(status_code=400, detail=f"Invalid format: {req.format}. Use json, csv, or html.")

    ext, exporter_fn = ext_map[req.format]

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, f"report{ext}")
        exporter_fn(root, i18n, output_path, scan_result)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=_EXPORT_MEDIA_TYPES[req.format],
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
                    label=drive_path,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent,
                ))
            except Exception:
                drives.append(DiskInfo(label=drive_path, total=0, used=0, free=0, percent=0))
    return drives


@router.get("/api/stats")
def get_stats(request: Request):
    root = _get_last_scan_root(request)

    return ScanStats(
        total_size=root.total_size,
        total_files=root.file_count,
        total_folders=root.folder_count,
        scan_path=root.path,
    )