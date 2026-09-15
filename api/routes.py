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
from folder_analyzer.exporter import (
    export_json_v2,
    export_csv_v2,
    export_html_v2,
    _assessment_to_dict,
    _build_recursive_compositions,
)
from folder_analyzer.i18n import I18n, REASONS, STRINGS
from folder_analyzer.engine.explain import resolve_reason

from .models import (
    ScanRequest, ScanResponse, ScanStats, FolderDict, AssessmentView,
    DeleteRequest, DeleteResponse, DeleteResult,
    ExportRequest, DiskInfo, FileDict, FolderFilesResponse, I18nResponse,
)

router = APIRouter()

_EXPORT_MEDIA_TYPES = {
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "html": "text/html; charset=utf-8",
}


def _norm_lang(lang: str | None) -> str:
    return lang if lang in ("en", "es") else "en"


def _assessment_view(assessment, lang: str) -> AssessmentView | None:
    """Localize a per-folder/per-file assessment for the UI: ``reason`` is the
    interpolated single-source locale text; never a raw reason_key."""
    if assessment is None:
        return None
    raw = _assessment_to_dict(assessment) or {}
    return AssessmentView(
        recommendation=raw.get("recommendation") or "",
        confidence=raw.get("confidence") or "",
        impact=raw.get("impact") or "",
        reason_key=raw.get("reason_key") or "",
        reason_params=raw.get("reason_params"),
        detected_category=raw.get("detected_category"),
        app_id=raw.get("app_id"),
        is_user_data=bool(raw.get("is_user_data")),
        is_temporary=bool(raw.get("is_temporary")),
        reason=resolve_reason(
            raw.get("reason_key") or "",
            lang=lang,
            params=raw.get("reason_params"),
        ),
    )


def _folder_to_dict(folder, per_folder=None, comps=None, lang: str = "en") -> FolderDict:
    risk = get_risk_level(folder.path)
    norm = os.path.normpath(folder.path)
    agg = per_folder.get(norm) if per_folder else None
    assessment = _assessment_view(agg.assessment if agg is not None else None, lang)
    composition = comps.get(norm) if comps else None
    return FolderDict(
        path=folder.path,
        name=folder.name,
        total_size=folder.total_size,
        file_count=folder.file_count,
        folder_count=folder.folder_count,
        direct_size=folder.direct_size,
        children=[_folder_to_dict(c, per_folder, comps, lang) for c in folder.children],
        error=folder.error,
        risk=risk.value,
        risk_color=get_risk_hex(risk),
        deletable=is_deletable(folder.path),
        assessment=assessment,
        composition=composition,
        recursive_total=composition["total_bytes"] if composition else None,
    )


def _file_view(record, lang: str) -> FileDict:
    """Serialize one retained record for the UI without re-classifying it."""
    assessment = getattr(record, "assessment", None)
    name = getattr(record, "filename", None) or os.path.basename(record.path)
    raw = _assessment_to_dict(assessment) if assessment is not None else None
    return FileDict(
        path=record.path,
        name=name,
        size=getattr(record, "size", 0) or 0,
        deletable=is_deletable(record.path),
        category=raw.get("detected_category") if raw else None,
        app_id=raw.get("app_id") if raw else None,
        is_user_data=bool(raw.get("is_user_data")) if raw else False,
        is_temporary=bool(raw.get("is_temporary")) if raw else False,
        recommendation=raw.get("recommendation", "") if raw else "",
        confidence=raw.get("confidence", "") if raw else "",
        impact=raw.get("impact", "") if raw else "",
        reason_key=raw.get("reason_key", "") if raw else "",
        reason=(
            resolve_reason(raw["reason_key"], lang=lang, params=raw.get("reason_params"))
            if raw and raw.get("reason_key")
            else ""
        ),
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
def scan_folder(req: ScanRequest, request: Request, lang: str = "en"):
    lang = _norm_lang(lang)
    path = os.path.normpath(req.path)
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")

    scanner = Scanner(max_workers=16)
    root = scanner.scan(path)
    scan_result = scanner.scan_result()
    request.app.state.last_scan_root = root
    request.app.state.last_scan_result = scan_result
    request.app.state.last_scanner = scanner

    comps = _build_recursive_compositions(root, scan_result.per_folder)
    root_dict = _folder_to_dict(root, scan_result.per_folder, comps, lang)
    # The scanned root is never a normal deletable item.
    root_dict.deletable = False

    top_folders_raw = sort_folders_by_size(root, top_n=50)
    top_folders = [_folder_to_dict(f, scan_result.per_folder, comps, lang) for f in top_folders_raw]

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
def get_folders(request: Request, limit: int = 50, lang: str = "en"):
    lang = _norm_lang(lang)
    root = _get_last_scan_root(request)
    scan_result = getattr(request.app.state, "last_scan_result", None)
    per_folder = scan_result.per_folder if scan_result is not None else None
    comps = _build_recursive_compositions(root, per_folder) if per_folder else None
    top = sort_folders_by_size(root, top_n=limit)
    return [_folder_to_dict(f, per_folder, comps, lang) for f in top]


@router.get("/api/i18n", response_model=I18nResponse)
def get_i18n(lang: str = "en"):
    lang = _norm_lang(lang)
    return I18nResponse(lang=lang, ui=STRINGS[lang], reasons=REASONS[lang])


@router.get("/api/folder/files", response_model=FolderFilesResponse)
def get_folder_files(request: Request, path: str, lang: str = "en"):
    """Per-folder retained file records for the UI.

    Zero re-classification (Phase 7): reads only the already-scan-retained
    records via ``Scanner.retained_records_for``; evicted folders return an
    empty list + ``evicted: true`` and the UI falls back to folder-level data.
    """
    lang = _norm_lang(lang)
    root = _get_last_scan_root(request)
    scanner = getattr(request.app.state, "last_scanner", None)
    if scanner is None:
        raise HTTPException(status_code=400, detail="No scan performed yet. POST /api/scan first.")

    norm = os.path.normpath(path)
    root_norm = os.path.normpath(root.path)
    if norm != root_norm and not norm.startswith(root_norm + os.sep):
        raise HTTPException(status_code=400, detail="Path is outside the scanned tree")

    scan_result = getattr(request.app.state, "last_scan_result", None)
    agg = scan_result.per_folder.get(norm) if scan_result is not None else None
    folder_assessment = _assessment_view(agg.assessment if agg is not None else None, lang)

    evicted = scanner.is_evicted(norm)
    files = (
        []
        if evicted
        else [_file_view(record, lang) for record in scanner.retained_records_for(norm)]
    )
    return FolderFilesResponse(
        folder_path=norm,
        evicted=evicted,
        files=files,
        folder_assessment=folder_assessment,
    )


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