"""Qt-free controller for the desktop UI (Phase 9).

Pure Python: no Qt imports, so the logic is unit-testable without a display
and the Qt layer stays a thin view. The core (``folder_analyzer/``) is
consumed strictly **in-process** (ADR-001).
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional

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


class DesktopController:
    def __init__(self, lang: str = "en"):
        self.i18n = I18n(lang)
        self._last_scan_root: Optional[str] = None
        self._last_tree = None

    def t(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def set_lang(self, lang: str):
        self.i18n.set_lang(lang)

    def scan(
        self,
        root_path: str,
        cancellation: Optional[ScanCancellation] = None,
    ) -> object:
        scanner = Scanner(max_workers=16)
        self._last_tree = scanner.scan(root_path, cancellation=cancellation)
        result = scanner.scan_result()
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

    @property
    def last_scan_root(self) -> Optional[str]:
        return self._last_scan_root