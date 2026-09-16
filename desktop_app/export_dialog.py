"""Export dialog (Phase 10, E1-E4).

Lets the user pick an export format (JSON/CSV/HTML) and a destination file;
on Save it emits ``export_requested`` and the main window delegates to
``DesktopController.export_report``, which calls the core
``folder_analyzer/exporter.py`` v2 functions. No export serialization logic
lives in the desktop package.
"""

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

_FORMAT_KEYS = (("json", "export_json"), ("csv", "export_csv"), ("html", "export_html"))


class ExportDialog(QDialog):
    export_requested = Signal(str, str)

    def __init__(self, t, default_dir: str = "", parent=None):
        super().__init__(parent)
        self._t = t
        self._default_dir = default_dir
        self._build()
        self.retranslate(t)

    def _build(self):
        layout = QVBoxLayout(self)

        self._title = QLabel(self)
        self._title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self._title)

        self._format_label = QLabel(self)
        self._format_combo = QComboBox(self)
        for fmt, key in _FORMAT_KEYS:
            self._format_combo.addItem("", fmt)
        format_row = QHBoxLayout()
        format_row.addWidget(self._format_label)
        format_row.addWidget(self._format_combo, 1)
        layout.addLayout(format_row)

        self._path_label = QLabel(self)
        self._path_input = QLineEdit(self)
        self._browse_button = QPushButton(self)
        self._browse_button.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self._path_label)
        path_row.addWidget(self._path_input, 1)
        path_row.addWidget(self._browse_button)
        layout.addLayout(path_row)

        buttons = QHBoxLayout()
        self._save_button = QPushButton(self)
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self._emit)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(self._save_button)
        buttons.addWidget(self._cancel_button)
        layout.addLayout(buttons)

        self._path_input.textChanged.connect(
            lambda text: self._save_button.setEnabled(bool(text.strip()))
        )

    def _browse(self):
        fmt = self._format_combo.currentData()
        default = os.path.join(
            self._default_dir, f"folder_analysis_report.{fmt}"
        ) if self._default_dir else f"folder_analysis_report.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("btn_export"),
            default,
            f"{fmt.upper()} (*.{fmt})",
        )
        if path:
            self._path_input.setText(os.path.normpath(path))

    def _emit(self):
        self.export_requested.emit(
            self._format_combo.currentData(), self._path_input.text().strip()
        )
        self.accept()

    def retranslate(self, t):
        self._t = t
        self.setWindowTitle(t("btn_export"))
        self._title.setText(t("btn_export"))
        self._format_label.setText(t("export_title"))
        self._path_label.setText(t("export_filename"))
        self._browse_button.setText(t("btn_browse"))
        self._save_button.setText(t("btn_save"))
        self._cancel_button.setText(t("btn_cancel"))
        for i, (fmt, key) in enumerate(_FORMAT_KEYS):
            self._format_combo.setItemText(i, t(key))