"""Controller unit tests for the desktop app (Phase 9).

The controller is Qt-free by design (ADR-001), so these tests run without a
display. Real classification assertions use the mandatory fixtures.
"""

import os

from desktop_app.controller import DesktopController
from folder_analyzer.scanner import ScanCancellation


def _rows_by_path(controller, root):
    result = controller.scan(root)
    rows = controller.rows(result)
    return result, {row["path"]: row for row in rows}


def test_rows_exclude_scan_root_and_localize(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    result, rows = _rows_by_path(controller, root)

    assert result.cancelled is False
    assert os.path.normpath(root) not in rows
    assert os.path.normpath(data) in rows
    assert os.path.normpath(cache) in rows


def test_safe_folder_under_review_folder_is_actionable(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    _, rows = _rows_by_path(controller, root)

    data_row = rows[os.path.normpath(data)]
    cache_row = rows[os.path.normpath(cache)]

    assert cache_row["action"] is True
    assert cache_row["rec_label"] == controller.t("rec_safe_to_delete")
    assert data_row["action"] is False

    reason = cache_row["reason"]
    assert reason
    assert "{" not in reason


def test_i10_bulk_gate_uses_folder_recommendation(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    result, _ = _rows_by_path(controller, root)

    data_assessment = result.per_folder[os.path.normpath(data)].assessment
    cache_assessment = result.per_folder[os.path.normpath(cache)].assessment

    assert controller.action_enabled(cache_assessment, deletable=True) is True
    assert controller.action_enabled(data_assessment, deletable=True) is False
    assert controller.action_enabled(cache_assessment, deletable=False) is False


def test_delete_wraps_security_guard_and_send2trash(mixed_sandbox, monkeypatch, tmp_path):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    controller.scan(root)

    sent = []
    monkeypatch.setattr("desktop_app.controller.send2trash", lambda p: sent.append(p))

    outside = tmp_path / "other"
    outside.mkdir()
    missing = str(tmp_path / "nope")

    outcomes = controller.delete_folders([missing])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_folders([str(outside)])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_folders([os.path.normpath(root)])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_folders([cache])
    assert outcomes[0]["status"] == "deleted"
    assert sent == [cache]


def test_precancelled_scan_is_explicit_partial(mixed_sandbox):
    root, _, _ = mixed_sandbox
    controller = DesktopController("en")
    token = ScanCancellation()
    token.cancel()

    result = controller.scan(root, cancellation=token)

    assert result.cancelled is True


def test_i18n_labels_follow_single_source_locale_files():
    controller_en = DesktopController("en")
    controller_es = DesktopController("es")

    assert controller_en.t("btn_scan") == "Scan"
    assert controller_es.t("btn_scan") == "Escanear"
    assert controller_en.t("desktop_pick_folder") != controller_es.t("desktop_pick_folder")
    assert controller_en.t("missing_key_xyz") == "missing_key_xyz"