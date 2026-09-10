"""Pydantic models for Folder Analyzer API."""

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str


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
