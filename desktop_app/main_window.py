"""Desktop main window (PySide6). Thin view over DesktopController.

Phase 9 shipped the scaffold; Phase 10 adds drill-down navigation on top of
the assessment table (D1-D5). All user-facing strings come from the
single-source locale files and the delete matrix / I10 hold in every surface.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from desktop_app.controller import DesktopController
from desktop_app.details_dialog import DetailsDialog
from desktop_app.worker import ScanWorker
from folder_analyzer.scanner import ScanCancellation
from folder_analyzer.utils import format_size

_COL_KEYS = (
    "col_folder",
    "col_size",
    "col_files",
    "col_recommendation",
    "col_confidence",
    "col_impact",
    "col_reason",
)
_FILE_COL_KEYS = (
    "col_name",
    "col_size",
    "col_recommendation",
    "col_confidence",
    "col_impact",
    "col_reason",
)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = DesktopController()
        self._worker = None
        self._result = None
        self._cancellation = None
        self._drill_folder = None
        self._folder_rows = []
        self._file_rows = []
        self._details_item = None
        self._details_dialog = None
        self._build_ui()
        self._retranslate()

    def _build_ui(self):
        self._toolbar = QToolBar(self)
        self.addToolBar(self._toolbar)

        self._pick_button = QPushButton(self)
        self._toolbar.addWidget(self._pick_button)
        self._pick_button.clicked.connect(self._pick_folder)

        self._path_input = QLineEdit(self)
        self._path_input.setMinimumWidth(320)
        self._toolbar.addWidget(self._path_input)

        self._lang_combo = QComboBox(self)
        for code in ("en", "es"):
            self._lang_combo.addItem(code.upper(), code)
        self._lang_combo.setCurrentIndex(0)
        self._toolbar.addWidget(self._lang_combo)
        self._lang_combo.currentIndexChanged.connect(self._change_lang)

        self._scan_button = QPushButton(self)
        self._scan_button.clicked.connect(self._start_scan)
        self._toolbar.addWidget(self._scan_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setEnabled(False)
        self._toolbar.addWidget(self._cancel_button)
        self._cancel_button.clicked.connect(self._cancel_scan)

        self._open_button = QPushButton(self)
        self._open_button.setEnabled(False)
        self._toolbar.addWidget(self._open_button)
        self._open_button.clicked.connect(self._open_drill_down)

        self._details_button = QPushButton(self)
        self._details_button.setEnabled(False)
        self._toolbar.addWidget(self._details_button)
        self._details_button.clicked.connect(self._open_details)

        self._delete_button = QPushButton(self)
        self._delete_button.setEnabled(False)
        self._toolbar.addWidget(self._delete_button)
        self._delete_button.clicked.connect(self._run_delete)

        self._stack = QStackedWidget(self)

        top_page = QWidget(self)
        top_layout = QVBoxLayout(top_page)

        self._notice = QLabel(self)
        self._notice.setWordWrap(True)
        self._notice.setStyleSheet(
            "color: #b00020; font-weight: bold; background: #fdecea; padding: 6px;"
        )
        self._notice.hide()
        top_layout.addWidget(self._notice)

        self._table = QTableWidget(0, len(_COL_KEYS), self)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 240)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 70)
        self._table.itemSelectionChanged.connect(self._update_action_state)
        top_layout.addWidget(self._table)

        self._stack.addWidget(top_page)
        self._top_page = top_page

        drill_page = QWidget(self)
        drill_layout = QVBoxLayout(drill_page)

        self._back_button = QPushButton(self)
        self._back_button.clicked.connect(self._back_to_top)
        drill_layout.addWidget(self._back_button)

        self._drill_title = QLabel(self)
        self._drill_title.setWordWrap(True)
        drill_layout.addWidget(self._drill_title)

        self._evicted_notice = QLabel(self)
        self._evicted_notice.setWordWrap(True)
        self._evicted_notice.setStyleSheet(
            "color: #b00020; font-weight: bold; background: #fdecea; padding: 6px;"
        )
        self._evicted_notice.hide()
        drill_layout.addWidget(self._evicted_notice)

        self._file_table = QTableWidget(0, len(_FILE_COL_KEYS), self)
        self._file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._file_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self._file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._file_table.verticalHeader().setVisible(False)
        self._file_table.horizontalHeader().setStretchLastSection(True)
        self._file_table.setColumnWidth(0, 240)
        self._file_table.setColumnWidth(1, 90)
        self._file_table.itemSelectionChanged.connect(self._update_action_state)
        drill_layout.addWidget(self._file_table)

        self._stack.addWidget(drill_page)
        self._drill_page = drill_page

        self.setCentralWidget(self._stack)
        self.resize(960, 520)

    def _retranslate(self):
        t = self.controller.t
        self.setWindowTitle(t("app_title"))
        self._pick_button.setText(t("desktop_pick_folder"))
        self._path_input.setPlaceholderText(t("scan_placeholder"))
        self._scan_button.setText(t("btn_scan"))
        self._cancel_button.setText(t("btn_cancel"))
        self._open_button.setText(t("desktop_open"))
        self._details_button.setText(t("desktop_details"))
        self._delete_button.setText(t("btn_recycle"))
        self._back_button.setText(t("desktop_back"))
        self._table.setHorizontalHeaderLabels([t(key) for key in _COL_KEYS])
        self._file_table.setHorizontalHeaderLabels(
            [t(key) for key in _FILE_COL_KEYS]
        )
        self.statusBar().showMessage(t("desktop_status_ready"))

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, self.controller.t("desktop_pick_folder")
        )
        if path:
            self._path_input.setText(os.path.normpath(path))

    def _change_lang(self):
        self._apply_lang(self._lang_combo.currentData())

    def _apply_lang(self, code):
        self.controller.set_lang(code)
        self._retranslate()
        if self._stack.currentWidget() is self._drill_page:
            self._populate_drill()
        elif self._result is not None:
            self._populate()
        if (
            self._details_item is not None
            and self._details_dialog is not None
            and self._details_dialog.isVisible()
        ):
            fresh = self._recompute_details_item(self._details_item["path"])
            if fresh is not None:
                self._details_item = fresh
                self._details_dialog.refresh(fresh)
        self._update_action_state()

    def _start_scan(self):
        path = self._path_input.text().strip()
        if not path:
            self.statusBar().showMessage(self.controller.t("empty_table_message"), 5000)
            return
        self._stack.setCurrentWidget(self._top_page)
        self._scan_button.setEnabled(False)
        self._set_notice(None)
        self._table.setRowCount(0)
        self._delete_button.setEnabled(False)
        self._cancellation = ScanCancellation()
        self._cancel_button.setEnabled(True)
        self.statusBar().showMessage(self.controller.t("scanning", path=path))
        self._worker = ScanWorker(
            self.controller, os.path.normpath(path), self._cancellation, self
        )
        self._worker.finished_ok.connect(self._on_scan_finished)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _cancel_scan(self):
        if self._cancellation is not None:
            self._cancellation.cancel()
            self._cancel_button.setEnabled(False)

    def _on_scan_finished(self, result):
        self._result = result
        self._stack.setCurrentWidget(self._top_page)
        self._populate()
        self._scan_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        if result.cancelled:
            self._set_notice(
                self.controller.t("scan_cancelled")
                + " "
                + self.controller.t(
                    "scan_cancelled_detail",
                    size=format_size(result.total_descendant_size),
                    count=result.files_analyzed,
                )
            )
            self.statusBar().showMessage(
                self.controller.t("scan_cancelled"), 5000
            )
        else:
            self.statusBar().showMessage(
                self.controller.t(
                    "scan_complete_detail",
                    size=format_size(result.total_descendant_size),
                    count=result.files_analyzed,
                ),
                5000,
            )
        self._update_action_state()
        self._cleanup_worker()

    def _on_scan_failed(self, message):
        self._scan_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        self.statusBar().showMessage(
            self.controller.t("scan_error_detail", message=message), 5000
        )
        self._cleanup_worker()

    def _cleanup_worker(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _populate(self):
        rows = self.controller.rows(self._result)
        self._folder_rows = rows
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = (
                row["name"],
                row["size"],
                str(row["files"]),
                row["rec_label"],
                row["conf_label"],
                row["imp_label"],
                row["reason"],
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                if col == 0:
                    item.setData(Qt.UserRole, row["path"])
                    item.setData(Qt.UserRole + 1, row["action"])
                    item.setToolTip(row["path"])
                self._table.setItem(i, col, item)

    # --- Phase 10: drill-down navigation (D1-D5) --------------------------

    def show_drill_down(self, path):
        self._drill_folder = os.path.normpath(path)
        self._stack.setCurrentWidget(self._drill_page)
        self._populate_drill()
        self._update_action_state()

    def _open_drill_down(self):
        path = self._selected_folder_path()
        if path:
            self.show_drill_down(path)

    def _back_to_top(self):
        self._stack.setCurrentWidget(self._top_page)
        self._update_action_state()

    def _selected_folder_path(self):
        for item in self._table.selectedItems():
            if item.column() == 0:
                return item.data(Qt.UserRole)
        return None

    def _selected_file_path(self):
        for item in self._file_table.selectedItems():
            if item.column() == 0:
                return item.data(Qt.UserRole)
        return None

    def _recompute_details_item(self, path: str) -> dict | None:
        """Re-derive a row dict for the details panel from the current scan
        and language (same controller helpers the tables use), so a live
        language switch re-localizes the open panel content."""
        if self._result is None:
            return None
        for row in self.controller.rows(self._result):
            if row["path"] == path:
                return row
        for row in self.controller.file_rows(os.path.dirname(path)):
            if row["path"] == path:
                return row
        return None

    def _open_details(self):
        if self._stack.currentWidget() is self._drill_page:
            path = self._selected_file_path()
        else:
            path = self._selected_folder_path()
        if path:
            self._show_details(path)

    def _show_details(self, path: str):
        item = self._recompute_details_item(path)
        if item is None:
            return
        self._details_item = item
        if self._details_dialog is not None and self._details_dialog.isVisible():
            self._details_dialog.refresh(item)
        else:
            self._details_dialog = DetailsDialog(
                self.controller.t, item, parent=self
            )
            self._details_dialog.show()

    def _populate_drill(self):
        self._file_rows = self.controller.file_rows(self._drill_folder)
        self._drill_title.setText(
            self.controller.t("folder_files_title", path=self._drill_folder)
        )
        rows = self._file_rows
        self._file_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = (
                row["name"],
                row["size"],
                row["rec_label"],
                row["conf_label"],
                row["imp_label"],
                row["reason"],
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                if col == 0:
                    item.setData(Qt.UserRole, row["path"])
                    item.setData(Qt.UserRole + 1, row["action"])
                    item.setToolTip(row["path"])
                self._file_table.setItem(i, col, item)
        if self.controller.is_evicted(self._drill_folder):
            self._evicted_notice.setText(self.controller.t("records_evicted"))
            self._evicted_notice.show()
        elif not rows:
            self._evicted_notice.setText(self.controller.t("desktop_no_files"))
            self._evicted_notice.show()
        else:
            self._evicted_notice.hide()

    # --- Delete matrix (DM) across top table and drill-down -----------------

    def _update_action_state(self):
        deletable = False
        openable = False
        detailsable = False
        if self._stack.currentWidget() is self._drill_page:
            for item in self._file_table.selectedItems():
                if item.column() == 0:
                    if item.data(Qt.UserRole + 1):
                        deletable = True
                    detailsable = True
                    break
            self._open_button.setEnabled(False)
        else:
            for item in self._table.selectedItems():
                if item.column() == 0:
                    if item.data(Qt.UserRole + 1):
                        deletable = True
                    openable = True
                    detailsable = True
                    break
            self._open_button.setEnabled(
                openable and self._result is not None
            )
        self._delete_button.setEnabled(deletable)
        self._details_button.setEnabled(
            detailsable and self._result is not None
        )

    def _run_delete(self):
        if self._stack.currentWidget() is self._drill_page:
            self._run_file_delete()
        else:
            self._run_folder_delete()

    def _run_folder_delete(self):
        selected = {
            item.data(Qt.UserRole)
            for item in self._table.selectedItems()
            if item.column() == 0 and item.data(Qt.UserRole)
        }
        attempts = []
        skipped = 0
        for path in selected:
            enabled = any(
                item.column() == 0
                and item.data(Qt.UserRole) == path
                and item.data(Qt.UserRole + 1)
                for item in self._table.selectedItems()
            )
            if not enabled:
                skipped += 1
                continue
            attempts.append(path)
        deleted = 0
        blocked = 0
        if attempts:
            results = self.controller.delete_folders(
                attempts, confirm=self._confirm_delete_folder
            )
            for outcome in results:
                if outcome["status"] == "deleted":
                    deleted += 1
                elif outcome["status"] == "blocked":
                    blocked += 1
                elif outcome["status"] == "error":
                    self.statusBar().showMessage(
                        self.controller.t(
                            "delete_failed",
                            path=outcome["path"],
                            error=outcome["reason"],
                        ),
                        5000,
                    )
        if blocked + skipped or deleted:
            self.statusBar().showMessage(
                self.controller.t(
                    "toast_delete_blocked", b=blocked + skipped, d=deleted
                ),
                5000,
            )
        self._update_action_state()

    def _run_file_delete(self):
        selected = {
            item.data(Qt.UserRole)
            for item in self._file_table.selectedItems()
            if item.column() == 0 and item.data(Qt.UserRole)
        }
        attempts = []
        skipped = 0
        for path in selected:
            enabled = any(
                item.column() == 0
                and item.data(Qt.UserRole) == path
                and item.data(Qt.UserRole + 1)
                for item in self._file_table.selectedItems()
            )
            if not enabled:
                skipped += 1
                continue
            attempts.append(path)
        deleted = 0
        blocked = 0
        if attempts:
            results = self.controller.delete_files(
                attempts, confirm=self._confirm_delete_file
            )
            for outcome in results:
                if outcome["status"] == "deleted":
                    deleted += 1
                elif outcome["status"] == "blocked":
                    blocked += 1
                elif outcome["status"] == "error":
                    self.statusBar().showMessage(
                        self.controller.t(
                            "delete_failed",
                            path=outcome["path"],
                            error=outcome["reason"],
                        ),
                        5000,
                    )
        if deleted and not (blocked + skipped):
            self.statusBar().showMessage(
                self.controller.t("deleted_files", count=deleted), 5000
            )
        elif deleted or blocked + skipped:
            self.statusBar().showMessage(
                self.controller.t(
                    "toast_delete_blocked", b=blocked + skipped, d=deleted
                ),
                5000,
            )
        self._populate_drill()
        self._update_action_state()

    def _confirm_delete_folder(self, path) -> bool:
        answer = QMessageBox.question(
            self,
            self.controller.t("confirm_delete_title"),
            self.controller.t("confirm_folder_body"),
        )
        return answer == QMessageBox.StandardButton.Yes

    def _confirm_delete_file(self, path) -> bool:
        answer = QMessageBox.question(
            self,
            self.controller.t("confirm_delete_title"),
            self.controller.t("confirm_file_body"),
        )
        return answer == QMessageBox.StandardButton.Yes

    def _set_notice(self, text: str | None):
        if text:
            self._notice.setText(text)
            self._notice.show()
        else:
            self._notice.clear()
            self._notice.hide()