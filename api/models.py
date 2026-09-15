"""Pydantic models for Folder Analyzer API."""

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str


class AssessmentView(BaseModel):
    """Per-folder / per-file v2 assessment served to the UI.

    ``reason`` is the LOCALIZED, interpolated text (single-source locale
    files); ``reason_key`` is carried for audit parity only and is never
    rendered by the web frontend.
    """

    recommendation: str = ""
    confidence: str = ""
    impact: str = ""
    reason_key: str = ""
    reason_params: dict | None = None
    detected_category: str | None = None
    app_id: str | None = None
    is_user_data: bool = False
    is_temporary: bool = False
    reason: str = ""


class FolderDict(BaseModel):
    path: str
    name: str
    total_size: int = 0
    file_count: int = 0
    folder_count: int = 0
    direct_size: int = 0
    children: list["FolderDict"] = Field(default_factory=list)
    error: str | None = None
    risk: str = "safe"
    risk_color: str = "#3fb950"
    deletable: bool = True
    assessment: "AssessmentView | None" = None
    composition: dict | None = None
    recursive_total: int | None = None


class ScanStats(BaseModel):
    total_size: int
    total_files: int
    total_folders: int
    scan_path: str


class ScanResponse(BaseModel):
    root: FolderDict
    stats: ScanStats
    top_folders: list[FolderDict]


class DeleteRequest(BaseModel):
    paths: list[str]


class DeleteResult(BaseModel):
    path: str
    success: bool
    error: str | None = None
    status: str = "attempted"
    reason: str | None = None


class DeleteResponse(BaseModel):
    deleted: list[DeleteResult]
    blocked: list[str]
    total_deleted: int
    total_blocked: int


class ExportRequest(BaseModel):
    format: str
    lang: str = "en"


class DiskInfo(BaseModel):
    label: str = ""
    total: int
    used: int
    free: int
    percent: float


class FileDict(BaseModel):
    """Per-file v2 row served to the UI (retained records only, zero
    re-classification). ``reason`` is localized; ``reason_key`` never
    rendered by the frontend. ``deletable`` is the OS/protection guard so the
    UI can enable/disable the single-file action."""

    path: str
    name: str
    size: int = 0
    deletable: bool = True
    category: str | None = None
    app_id: str | None = None
    is_user_data: bool = False
    is_temporary: bool = False
    recommendation: str = ""
    confidence: str = ""
    impact: str = ""
    reason_key: str = ""
    reason: str = ""


class FolderFilesResponse(BaseModel):
    folder_path: str
    evicted: bool
    files: list[FileDict]
    folder_assessment: "AssessmentView | None" = None


class I18nResponse(BaseModel):
    lang: str
    ui: dict[str, str]
    reasons: dict[str, str]
