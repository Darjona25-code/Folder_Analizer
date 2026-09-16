"""Read-only reasons/details panel (Phase 10, R1-R4).

Displays an item's recommendation, confidence, impact and the full localized
reason exactly as the owning table row renders them (same controller-built
row dict; single source, no parallel reason logic). Deliberately display-only:
this is the delete matrix's ``Review`` affordance and never a delete path —
no delete button exists anywhere in this dialog (R3).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DetailsDialog(QDialog):
    def __init__(self, t, item: dict, parent=None):
        super().__init__(parent)
        self._t = t
        self._item = None
        self.setMinimumWidth(520)
        self._build()
        self.refresh(item)

    def _build(self):
        layout = QVBoxLayout(self)

        self._title = QLabel(self)
        self._title.setWordWrap(True)
        self._title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self._title)

        form = QFormLayout()

        def _wrap() -> QLabel:
            label = QLabel(self)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return label

        self._name_heading = QLabel(self)
        self._size_heading = QLabel(self)
        self._rec_heading = QLabel(self)
        self._conf_heading = QLabel(self)
        self._imp_heading = QLabel(self)
        self._reason_heading = QLabel(self)

        self._name_value = _wrap()
        self._size_value = _wrap()
        self._rec_value = _wrap()
        self._conf_value = _wrap()
        self._imp_value = _wrap()
        self._reason_value = _wrap()

        form.addRow(self._name_heading, self._name_value)
        form.addRow(self._size_heading, self._size_value)
        form.addRow(self._rec_heading, self._rec_value)
        form.addRow(self._conf_heading, self._conf_value)
        form.addRow(self._imp_heading, self._imp_value)
        form.addRow(self._reason_heading, self._reason_value)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(self._close_button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def refresh(self, item: dict):
        """Re-render from a controller-built row dict (localized labels)."""
        self._item = item
        t = self._t
        self.setWindowTitle(t("folder_details", path=item.get("path", "")))
        self._name_heading.setText(t("col_name"))
        self._size_heading.setText(t("col_size"))
        self._rec_heading.setText(t("col_recommendation"))
        self._conf_heading.setText(t("col_confidence"))
        self._imp_heading.setText(t("col_impact"))
        self._reason_heading.setText(t("col_reason"))
        self._name_value.setText(str(item.get("name", "")))
        self._size_value.setText(str(item.get("size", "")))
        self._rec_value.setText(str(item.get("rec_label", "")))
        self._conf_value.setText(str(item.get("conf_label", "")))
        self._imp_value.setText(str(item.get("imp_label", "")))
        self._reason_value.setText(str(item.get("reason", "")))
        self._close_button.setText(t("btn_cancel"))