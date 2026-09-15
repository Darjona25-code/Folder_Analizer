"""Desktop main window (PySide6). Thin view over DesktopController."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from desktop_app.controller import DesktopController
from desktop_app.worker import ScanWorker
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


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = DesktopController()
        self._worker = None
        self._result = None
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
        self._toolbar.addWidget(self._lang_combo)
        self._lang_combo.currentIndexChanged.connect(self._change_lang)

        self._scan_button = QPushButton(self)
        self._scan_button.clicked.connect(self._start_scan)
        self._toolbar.addWidget(self._scan_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setEnabled(False)
        self._toolbar.addWidget(self._cancel_button)

        self._delete_button = QPushButton(self)
        self._delete_button.setEnabled(False)
        self._toolbar.addWidget(self._delete_button)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        self._notice = QLabel(self)
        self._notice.setWordWrap(True)
        self._notice.setStyleSheet(
            "color: #b00020; font-weight: bold; background: #fdecea; padding: 6px;"
        )
        self._notice.hide()
        layout.addWidget(self._notice)

        self._table = QTableWidget(0, len(_COL_KEYS), self)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 240)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 70)
        layout.addWidget(self._table)

        self.setCentralWidget(central)
        self.resize(960, 520)

    def _retranslate(self):
        t = self.controller.t
        self.setWindowTitle(t("app_title"))
        self._pick_button.setText(t("desktop_pick_folder"))
        self._path_input.setPlaceholderText(t("scan_placeholder"))
        self._scan_button.setText(t("btn_scan"))
        self._cancel_button.setText(t("btn_cancel"))
        self._delete_button.setText(t("btn_recycle"))
        self._table.setHorizontalHeaderLabels([t(key) for key in _COL_KEYS])
        self.statusBar().showMessage(t("desktop_status_ready"))

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, self.controller.t("desktop_pick_folder")
        )
        if path:
            self._path_input.setText(os.path.normpath(path))

    def _change_lang(self):
        code = self._lang_combo.currentData()
        self.controller.set_lang(code)
        self._retranslate()

    def _start_scan(self):
        path = self._path_input.text().strip()
        if not path:
            self.statusBar().showMessage(self.controller.t("empty_table_message"), 5000)
            return
        self._scan_button.setEnabled(False)
        self._set_notice(None)
        self._table.setRowCount(0)
        self._delete_button.setEnabled(False)
        self.statusBar().showMessage(self.controller.t("scanning", path=path))
        self._worker = ScanWorker(self.controller, os.path.normpath(path), None, self)
        self._worker.finished_ok.connect(self._on_scan_finished)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _on_scan_finished(self, result):
        self._result = result
        self._populate()
        self._scan_button.setEnabled(True)
        self.statusBar().showMessage(
            self.controller.t(
                "scan_complete_detail",
                size=format_size(result.total_descendant_size),
                count=result.files_analyzed,
            ),
            5000,
        )
        self._cleanup_worker()

    def _on_scan_failed(self, message):
        self._scan_button.setEnabled(True)
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

    def _set_notice(self, text: str | None):
        if text:
            self._notice.setText(text)
            self._notice.show()
        else:
            self._notice.clear()
            self._notice.hide()