"""Qt-free controller for the desktop UI (Phase 9; extended in Phase 10).

Pure Python: no Qt imports, so the logic is unit-testable without a display
and the Qt layer stays a thin view. The core (``folder_analyzer/``) is
consumed strictly **in-process** (ADR-001).

Phase 10 surface:
- ``file_rows`` / ``is_evicted``: drill-down data populated exclusively from
  ``Scanner.retained_records_for`` (zero re-classification, Phase 7
  precedent); evicted folders yield no file rows and callers show the
  folder-level-only notice.
- ``delete_files`` routes through the SAME guarded path as ``delete_folders``
  (``validate_delete_target`` -> confirm -> ``revalidate`` -> ``send2trash``),
  so drill-down file actions share the six-condition safety guard.
- ``export_report`` is a thin wrapper over the existing
  ``folder_analyzer/exporter.py`` v2 functions; no export logic lives here.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional

from send2trash import send2trash

from folder_analyzer.engine.enums import DeletionRecommendation
from folder_analyzer.engine.explain import resolve_reason
from folder_analyzer.i18n import I18n
from folder_analyzer.safety import is_deletable
from folder_analyzer.scanner import ScanCancellation, Scanner
from folder_analyzer.utils import format_size

_REC_KEYS = {
    DeletionRecommendation.SAFE_TO_DELETE.value: "rec_safe_to_delete",
    DeletionRecommendation.REVIEW_FIRST.value: "rec_review_first",
    DeletionRecommendation.KEEP.value: "rec_keep",
    DeletionRecommendation.DO_NOT_DELETE.value: "rec_do_not_delete",
}
_CONF_KEYS = {"high": "conf_high", "medium": "conf_medium", "low": "conf_low"}
_IMP_KEYS = {
    "none": "imp_none",
    "low": "imp_low",
    "moderate": "imp_moderate",
    "high": "imp_high",
    "critical": "imp_critical",
    "unknown": "imp_unknown",
}

_EXPORT_FORMATS = ("json", "csv", "html")


class DesktopController:
    def __init__(self, lang: str = "en"):
        self.i18n = I18n(lang)
        self._last_scan_root: Optional[str] = None
        self._last_tree = None
        self._last_result = None
        self._scanner: Optional[Scanner] = None

    def t(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def set_lang(self, lang: str):
        self.i18n.set_lang(lang)

    def scan(
        self,
        root_path: str,
        cancellation: Optional[ScanCancellation] = None,
        retention=None,
    ) -> object:
        scanner = Scanner(max_workers=16, retention=retention)
        self._scanner = scanner
        self._last_tree = scanner.scan(root_path, cancellation=cancellation)
        result = scanner.scan_result()
        self._last_result = result
        self._last_scan_root = result.root_path
        return result

    def rows(self, result) -> List[dict]:
        from folder_analyzer.scanner import sort_folders_by_size

        rows: List[dict] = []
        for folder in sort_folders_by_size(self._last_tree, top_n=1 << 30):
            rows.append(self._row(folder, result))
        return rows

    def _row(self, folder, result) -> dict:
        norm = os.path.normpath(folder.path)
        agg = result.per_folder.get(norm) if result.per_folder else None
        assessment = agg.assessment if agg is not None else None
        return {
            "path": folder.path,
            "name": folder.name,
            "size": format_size(folder.total_size),
            "size_bytes": folder.total_size,
            "files": folder.file_count,
            "rec_label": self._rec_label(assessment),
            "conf_label": self._conf_label(assessment),
            "imp_label": self._imp_label(assessment),
            "reason": self._reason(assessment),
            "deletable": is_deletable(folder.path),
            "action": self.action_enabled(assessment, is_deletable(folder.path)),
        }

    def _rec_label(self, assessment) -> str:
        if assessment is None:
            return self.t("no_data")
        key = _REC_KEYS.get(assessment.recommendation.value, "")
        return self.t(key) if key else self.t("no_data")

    def _conf_label(self, assessment) -> str:
        if assessment is None:
            return self.t("no_data")
        key = _CONF_KEYS.get(assessment.confidence.value, "")
        return self.t(key) if key else self.t("no_data")

    def _imp_label(self, assessment) -> str:
        if assessment is None:
            return self.t("no_data")
        key = _IMP_KEYS.get(assessment.impact.value, "")
        return self.t(key) if key else self.t("no_data")

    def _reason(self, assessment) -> str:
        if assessment is None or not getattr(assessment, "reason_key", ""):
            return self.t("no_data")
        return resolve_reason(
            assessment.reason_key,
            lang=self.i18n.lang,
            params=getattr(assessment, "reason_params", None),
        )

    def action_enabled(self, assessment, deletable: bool) -> bool:
        return (
            deletable
            and assessment is not None
            and assessment.recommendation is DeletionRecommendation.SAFE_TO_DELETE
        )

    # --- Phase 10: drill-down (read-only, retained records only) -----------

    def file_rows(self, folder_path: str) -> List[dict]:
        """File rows for the drill-down view.

        Uses ``Scanner.retained_records_for`` (no re-analysis, Phase 7
        precedent). Evicted folders return an empty list so the UI falls back
        to the folder-level-only view, exactly like the web surface.
        """
        if self._scanner is None:
            return []
        if self.is_evicted(folder_path):
            return []
        rows = [
            self._file_row(record)
            for record in self._scanner.retained_records_for(folder_path)
        ]
        rows.sort(key=lambda r: (-r["size_bytes"], r["path"]))
        return rows

    def _file_row(self, record) -> dict:
        assessment = getattr(record, "assessment", None)
        name = getattr(record, "filename", None) or os.path.basename(record.path)
        size = getattr(record, "size", 0) or 0
        deletable = is_deletable(record.path)
        return {
            "path": record.path,
            "name": name,
            "size": format_size(size),
            "size_bytes": size,
            "rec_label": self._rec_label(assessment),
            "conf_label": self._conf_label(assessment),
            "imp_label": self._imp_label(assessment),
            "reason": self._reason(assessment),
            "deletable": deletable,
            "action": self.action_enabled(assessment, deletable),
        }

    def is_evicted(self, folder_path: str) -> bool:
        return bool(self._scanner and self._scanner.is_evicted(folder_path))

    # --- Phase 10: gated deletion (single shared guarded path) -------------

    def _guarded_delete(self, path: str, confirm: Optional[Callable]) -> dict:
        from folder_analyzer.security_guard import (
            GuardStatus,
            revalidate,
            validate_delete_target,
        )

        verdict = validate_delete_target(path, scan_root=self._last_scan_root)
        if verdict.status is not GuardStatus.OK:
            return {"path": path, "status": "blocked", "reason": verdict.reason}
        if confirm is not None and not confirm(path):
            return {"path": path, "status": "cancelled"}
        final = revalidate(path, scan_root=self._last_scan_root)
        if not final.ok:
            return {"path": path, "status": "blocked", "reason": final.reason}
        try:
            send2trash(path)
            return {"path": path, "status": "deleted"}
        except Exception as exc:
            return {"path": path, "status": "error", "reason": str(exc)}

    def delete_folders(
        self,
        paths: List[str],
        confirm: Optional[Callable] = None,
    ) -> List[dict]:
        return [self._guarded_delete(path, confirm) for path in paths]

    def delete_files(
        self,
        paths: List[str],
        confirm: Optional[Callable] = None,
    ) -> List[dict]:
        """File deletion in drill-down routes through the SAME guarded path
        as folder deletion (no parallel/shortcut delete logic)."""
        return [self._guarded_delete(path, confirm) for path in paths]

    # --- Phase 10: export (reuses folder_analyzer/exporter.py v2) ----------

    def export_report(
        self,
        report_format: str,
        output_path: str,
        scan_date: Optional[str] = None,
    ) -> dict:
        """Write an export for the in-memory scan via the core v2 exporters.

        Zero export logic here: delegates to ``export_json_v2`` /
        ``export_csv_v2`` / ``export_html_v2`` with the scan-time ScanResult
        and the single-source I18n.
        """
        if self._last_tree is None or self._last_result is None:
            return {"status": "error", "reason": "no_scan"}
        if report_format not in _EXPORT_FORMATS:
            return {"status": "error", "reason": "invalid_format"}
        from folder_analyzer.exporter import (
            export_csv_v2,
            export_html_v2,
            export_json_v2,
        )

        exporter_fn = {
            "json": export_json_v2,
            "csv": export_csv_v2,
            "html": export_html_v2,
        }[report_format]
        try:
            exporter_fn(
                self._last_tree,
                self.i18n,
                output_path,
                self._last_result,
                scan_date=scan_date,
            )
            return {"status": "ok", "path": output_path}
        except Exception as exc:
            return {"status": "error", "reason": str(exc)}

    @property
    def last_scan_root(self) -> Optional[str]:
        return self._last_scan_root