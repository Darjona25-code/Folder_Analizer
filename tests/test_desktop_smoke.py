"""Offscreen Qt smoke tests for the desktop UI (Phase 9).

Run headless via ``QT_QPA_PLATFORM=offscreen`` (set before any Qt import).
Real classification assertions use the mandatory fixtures per the project
test conventions.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

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


def test_window_builds_offscreen(qapp):
    window = MainWindow()
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


def test_offscreen_scan_populates_table_and_gates_delete(qapp, mixed_sandbox):
    root, data, cache = mixed_sandbox
    window = MainWindow()
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


def test_offscreen_cancelled_scan_shows_partial_notice(qapp, mixed_sandbox):
    root, _, _ = mixed_sandbox
    window = MainWindow()
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