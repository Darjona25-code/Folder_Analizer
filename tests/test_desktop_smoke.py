"""Offscreen Qt smoke tests for the desktop UI (Phase 9; Phase 10 surfaces).

Run headless via ``QT_QPA_PLATFORM=offscreen`` (set before any Qt import).
Real classification assertions use the mandatory fixtures per the project
test conventions. Every window is constructed with a temporary config path so
the real user settings file is never read or written.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop_app.main_window import MainWindow  # noqa: E402
from folder_analyzer.scanner import ScanCancellation  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _wait_for_scan(window, app, timeout=120.0):
    deadline = time.time() + timeout
    while window._worker is not None and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()


def _cfg(tmp_path) -> str:
    return str(tmp_path / "cfg.json")


def test_window_builds_offscreen(qapp, tmp_path):
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        assert window.windowTitle() == window.controller.t("app_title")
        assert window._table.columnCount() == 7
        assert window._table.horizontalHeaderItem(0).text() == "Folder"
        assert window._scan_button.text() == window.controller.t("btn_scan")
        assert window._delete_button.isEnabled() is False
        assert window._cancel_button.isEnabled() is False
    finally:
        window.close()
        window.deleteLater()


def test_offscreen_scan_populates_table_and_gates_delete(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        window._path_input.setText(root)
        window._start_scan()
        _wait_for_scan(window, qapp)

        assert window._result.cancelled is False
        assert window._table.rowCount() > 0

        rows_by_path = {}
        for i in range(window._table.rowCount()):
            item = window._table.item(i, 0)
            path = item.data(Qt.UserRole)
            rows_by_path[path] = i

        cache_row = rows_by_path[os.path.normpath(cache)]
        data_row = rows_by_path[os.path.normpath(data)]

        window._table.selectRow(data_row)
        qapp.processEvents()
        assert window._delete_button.isEnabled() is False

        window._table.clearSelection()
        window._table.selectRow(cache_row)
        qapp.processEvents()
        assert window._delete_button.isEnabled() is True
    finally:
        window.close()
        window.deleteLater()


def test_offscreen_cancelled_scan_shows_partial_notice(qapp, mixed_sandbox, tmp_path):
    root, _, _ = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        token = ScanCancellation()
        token.cancel()
        result = window.controller.scan(root, cancellation=token)
        assert result.cancelled is True

        window._on_scan_finished(result)
        qapp.processEvents()

        assert window._notice.isVisible()
        assert window.controller.t("scan_cancelled") in window._notice.text()

        window._set_notice(None)
        window._on_scan_finished(window.controller.scan(root))
        qapp.processEvents()
        assert window._notice.isVisible() is False
    finally:
        window.close()
        window.deleteLater()


def test_drill_down_shows_retained_files_with_i10_gates(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        window._path_input.setText(root)
        window._start_scan()
        _wait_for_scan(window, qapp)
        assert window._result.cancelled is False

        window.show_drill_down(data)
        qapp.processEvents()
        assert window._file_table.rowCount() == 1
        assert window._file_table.item(0, 0).text() == "notes.txt"
        assert window._open_button.isEnabled() is False

        window._file_table.selectRow(0)
        qapp.processEvents()
        assert window._delete_button.isEnabled() is False

        window.show_drill_down(cache)
        qapp.processEvents()
        assert window._file_table.rowCount() == 2
        names = [window._file_table.item(i, 0).text() for i in range(2)]
        assert set(names) == {"a.tmp", "b.tmp"}

        window._file_table.clearSelection()
        row = next(
            i
            for i in range(2)
            if window._file_table.item(i, 0).text() == "a.tmp"
        )
        window._file_table.selectRow(row)
        qapp.processEvents()
        assert window._delete_button.isEnabled() is True

        window._back_to_top()
        qapp.processEvents()
        assert window._stack.currentWidget() is window._top_page
        cache_row_on_top = next(
            i
            for i in range(window._table.rowCount())
            if window._table.item(i, 0).data(Qt.UserRole)
            == os.path.normpath(cache)
        )
        window._table.selectRow(cache_row_on_top)
        qapp.processEvents()
        assert window._open_button.isEnabled() is True
    finally:
        window.close()
        window.deleteLater()


def test_drill_down_evicted_folder_shows_folder_level_notice(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    bulk = os.path.join(root, "bulk")
    os.makedirs(bulk)
    for i in range(240):
        with open(os.path.join(bulk, f"junk{i:03d}.bak"), "w", encoding="utf-8") as fh:
            fh.write("x")

    from folder_analyzer.engine.retention import RetentionConfig

    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        result = window.controller.scan(
            root, retention=RetentionConfig(global_budget=1)
        )
        window._on_scan_finished(result)
        qapp.processEvents()

        window.show_drill_down(bulk)
        qapp.processEvents()
        assert window._file_table.rowCount() == 0
        assert window._evicted_notice.isVisible()
        assert window._evicted_notice.text() == window.controller.t("records_evicted")
    finally:
        window.close()
        window.deleteLater()


def test_drill_down_relocalizes_on_language_switch(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        window._path_input.setText(root)
        window._start_scan()
        _wait_for_scan(window, qapp)
        assert window._result.cancelled is False

        window.show_drill_down(cache)
        qapp.processEvents()
        assert window._file_table.horizontalHeaderItem(0).text() == "Name"

        window._lang_combo.setCurrentIndex(1)
        qapp.processEvents()
        assert window.controller.i18n.lang == "es"
        assert (
            window._file_table.horizontalHeaderItem(0).text()
            == window.controller.t("col_name")
        )
        assert window._file_table.item(0, 5).text()

        window._lang_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert (
            window._file_table.horizontalHeaderItem(0).text()
            == window.controller.t("col_name")
        )
    finally:
        window.close()
        window.deleteLater()


def test_details_panel_matches_row_values(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        window._path_input.setText(root)
        window._start_scan()
        _wait_for_scan(window, qapp)
        assert window._result.cancelled is False

        rows = window.controller.rows(window._result)
        cache_row = next(r for r in rows if r["path"] == os.path.normpath(cache))

        window._show_details(os.path.normpath(cache))
        qapp.processEvents()
        dialog = window._details_dialog
        assert dialog is not None and dialog.isVisible()

        assert dialog._name_value.text() == cache_row["name"]
        assert dialog._size_value.text() == cache_row["size"]
        assert dialog._rec_value.text() == cache_row["rec_label"]
        assert dialog._conf_value.text() == cache_row["conf_label"]
        assert dialog._imp_value.text() == cache_row["imp_label"]
        assert dialog._reason_value.text() == cache_row["reason"]

        delete_buttons = [
            w
            for w in dialog.findChildren(QPushButton)
            if w is not dialog._close_button
        ]
        assert delete_buttons == []
    finally:
        window.close()
        window.deleteLater()


def test_details_panel_relocalizes_on_language_switch(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        window._path_input.setText(root)
        window._start_scan()
        _wait_for_scan(window, qapp)

        window._show_details(os.path.normpath(cache))
        qapp.processEvents()
        dialog = window._details_dialog
        assert dialog._rec_value.text() == window.controller.t("rec_safe_to_delete")

        window._lang_combo.setCurrentIndex(1)
        qapp.processEvents()
        assert window.controller.i18n.lang == "es"
        assert dialog._rec_value.text() == window.controller.t("rec_safe_to_delete")
        assert dialog._name_heading.text() == window.controller.t("col_name")
        assert dialog._reason_value.text()

        window._lang_combo.setCurrentIndex(0)
        qapp.processEvents()
    finally:
        window.close()
        window.deleteLater()


def test_export_dialog_writes_validated_reports(qapp, mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    window = MainWindow(config_path=_cfg(tmp_path))
    window.show()
    qapp.processEvents()
    try:
        window._path_input.setText(root)
        window._start_scan()
        _wait_for_scan(window, qapp)
        assert window._result.cancelled is False
        assert window._export_button.isEnabled() is True

        window._open_export()
        qapp.processEvents()
        dlg = window._export_dialog
        assert dlg is not None and dlg.isVisible()
        assert dlg._format_combo.count() == 3

        import json

        dlg._format_combo.setCurrentIndex(0)
        out = str(tmp_path / "desktop_report.json")
        dlg._path_input.setText(out)
        qapp.processEvents()
        assert dlg._save_button.isEnabled() is True

        dlg._emit()
        qapp.processEvents()
        assert os.path.exists(out)
        payload = json.loads(
            (tmp_path / "desktop_report.json").read_text(encoding="utf-8")
        )
        assert payload["schema_version"] == 2
        assert payload["root_path"] == os.path.normpath(root)
        assert (
            window.statusBar().currentMessage()
            == window.controller.t("export_success", path=os.path.normpath(out))
        )
    finally:
        window.close()
        window.deleteLater()


def test_settings_dialog_applies_persists_and_restores_language(
    qapp, mixed_sandbox, tmp_path
):
    cfg = _cfg(tmp_path)
    window = MainWindow(config_path=cfg)
    window.show()
    qapp.processEvents()
    try:
        assert window.controller.i18n.lang == "en"

        window._open_settings()
        qapp.processEvents()
        dlg = window._settings_dialog
        assert dlg is not None and dlg.isVisible()
        assert dlg._lang_label.text() == window.controller.t("settings_language")

        dlg._lang_combo.setCurrentIndex(1)
        qapp.processEvents()
        assert window.controller.i18n.lang == "es"
        assert window._table.horizontalHeaderItem(0).text() == "Carpeta"
        assert window._lang_combo.currentData() == "es"
        assert dlg._lang_label.text() == window.controller.t("settings_language")

        from desktop_app.settings import AppSettings

        assert AppSettings(cfg).load_language() == "es"

        window.close()
        window.deleteLater()

        relaunched = MainWindow(config_path=cfg)
        try:
            assert relaunched.controller.i18n.lang == "es"
            assert relaunched._table.horizontalHeaderItem(0).text() == "Carpeta"
        finally:
            relaunched.close()
            relaunched.deleteLater()
    finally:
        window.close()
        window.deleteLater()