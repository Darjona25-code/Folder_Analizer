"""Application bootstrap for the Folder Analyzer desktop window."""

import sys

from PySide6.QtWidgets import QApplication

from desktop_app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()