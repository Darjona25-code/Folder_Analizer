"""Append-only JSON Lines deletion audit log (Phase 1).

Records every deletion attempt, including denied and deferred ones. The file is
append-only: each record is a single JSON line, written with the file opened in
append mode. No in-place mutation ever happens.

User-facing output must keep showing the original human-readable path; the
optional ``canonical_path`` field is recorded for auditing/operations only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional


class DeletionAuditor:
    """Append-only audit log writer."""

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or os.environ.get(
            "FOLDER_ANALYZER_AUDIT_LOG", "deletion_audit.jsonl"
        )

    def record(
        self,
        *,
        status: str,
        original: str,
        canonical: Optional[str] = None,
        reason: str = "",
        success: Optional[bool] = None,
        risk: Optional[str] = None,
    ) -> dict:
        """Append a single audit entry and return it."""
        entry = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "path": original,
            "canonical_path": canonical,
            "reason": reason,
            "risk": risk,
        }
        if success is not None:
            entry["success"] = success

        directory = os.path.dirname(os.path.abspath(self.log_path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry