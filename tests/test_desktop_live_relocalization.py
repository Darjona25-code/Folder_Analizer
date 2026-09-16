"""Live EN/ES re-localization inside ONE running session (Phase 11 residual L2).

Proves the runtime language path of a single continuously-running
QApplication + MainWindow instance: the language combo (or settings dialog)
is switched while the process runs — never restarted — and the SAME widget
objects re-render UI-facing strings, the SAME ``I18n`` instance is mutated in
place (no re-creation), and the language persists to the config file.

Complementary artifact-level evidence (option 'a', UI Automation driving the
frozen ``dist/FolderAnalyzer.exe`` in a single process) is captured by the
disposable probe ``l2_probe_artifact.py`` (one-off, NOT committed); this test
locks the same behavior at source level inside the committed suite.
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop_app.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _cfg(tmp_path) -> str:
    return str(tmp_path / "cfg.json")


def test_live_relocalization_in_one_running_session(qapp, tmp_path):
    cfg = _cfg(tmp_path)
    window = MainWindow(config_path=cfg)
    window.show()
    qapp.processEvents()
    try:
        i18n = window.controller.i18n
        i18n_id_before = id(i18n)
        header0 = window._table.horizontalHeaderItem(0)
        assert window.windowTitle() == "Folder Analyzer"
        assert header0.text() == "Folder"
        assert window.controller.t("col_name") == "Name"
        assert window.statusBar().currentMessage() == "Ready"
        assert window._scan_button.text() == "Scan"

        print(
            "BEFORE(lang=%s, i18n_id=%x): title=%r col_folder=%r col_name=%r "
            "status=%r scan=%r" % (
                i18n.lang, i18n_id_before,
                window.windowTitle(), header0.text(),
                window.controller.t("col_name"),
                window.statusBar().currentMessage(),
                window._scan_button.text(),
            )
        )

        window._lang_combo.setCurrentIndex(1)
        qapp.processEvents()

        assert window.controller.i18n is i18n
        assert id(window.controller.i18n) == i18n_id_before
        assert i18n.lang == "es"
        assert window.windowTitle() == "Analizador de Carpetas"
        assert header0.text() == "Carpeta"
        assert window.controller.t("col_name") == "Nombre"
        assert window.statusBar().currentMessage() == "Listo"
        assert window._scan_button.text() == "Escanear"

        print(
            "AFTER_ES(lang=%s, i18n_id=%x): title=%r col_folder=%r col_name=%r "
            "status=%r scan=%r" % (
                i18n.lang, id(window.controller.i18n),
                window.windowTitle(), header0.text(),
                window.controller.t("col_name"),
                window.statusBar().currentMessage(),
                window._scan_button.text(),
            )
        )

        saved = json.loads(__import__("pathlib").Path(cfg).read_text(encoding="utf-8"))
        assert saved == {"language": "es"}

        window._lang_combo.setCurrentIndex(0)
        qapp.processEvents()

        assert window.controller.i18n is i18n
        assert i18n.lang == "en"
        assert window.windowTitle() == "Folder Analyzer"
        assert header0.text() == "Folder"
        assert window.controller.t("col_name") == "Name"

        print(
            "AFTER_BACK_EN(lang=%s, i18n_id=%x): title=%r col_folder=%r "
            "col_name=%r" % (
                i18n.lang, id(window.controller.i18n),
                window.windowTitle(), header0.text(),
                window.controller.t("col_name"),
            )
        )

        saved = json.loads(__import__("pathlib").Path(cfg).read_text(encoding="utf-8"))
        assert saved == {"language": "en"}
    finally:
        window.close()
        window.deleteLater()
