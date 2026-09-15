"""Background scan worker (PySide6). Bridges the Qt-free controller to the UI."""

from PySide6.QtCore import QThread, Signal

from folder_analyzer.scanner import ScanCancellation


class ScanWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        controller,
        root_path: str,
        cancellation: ScanCancellation | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._root_path = root_path
        self._cancellation = cancellation

    def run(self):
        try:
            result = self._controller.scan(self._root_path, cancellation=self._cancellation)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))