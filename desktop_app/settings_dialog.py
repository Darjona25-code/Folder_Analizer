"""Settings dialog (Phase 10, S1-S2).

Exposes the single approved preference: the UI language (EN/ES). Changes are
applied live (``language_applied``) and the main window persists them via
``AppSettings``; the dialog itself holds no persistence logic.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    language_changed = Signal(str)

    def __init__(self, t, current_lang: str = "en", parent=None):
        super().__init__(parent)
        self._t = t
        self._build()
        self._lang_combo.setCurrentIndex(0 if current_lang == "en" else 1)
        self.retranslate(t)

    def _build(self):
        layout = QVBoxLayout(self)

        self._title = QLabel(self)
        self._title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self._title)

        row = QHBoxLayout()
        self._lang_label = QLabel(self)
        self._lang_combo = QComboBox(self)
        for code in ("en", "es"):
            self._lang_combo.addItem(code.upper(), code)
        self._lang_combo.currentIndexChanged.connect(self._emit)
        row.addWidget(self._lang_label)
        row.addWidget(self._lang_combo, 1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(self._close_button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def _emit(self):
        self.language_changed.emit(self._lang_combo.currentData())

    def retranslate(self, t):
        self._t = t
        self.setWindowTitle(t("desktop_settings"))
        self._title.setText(t("desktop_settings"))
        self._lang_label.setText(t("settings_language"))
        self._close_button.setText(t("btn_cancel"))