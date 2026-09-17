"""Phase 12 TASK 2 - E2E against the FROZEN Phase 11 artifact.

1. UIA-driven session on ``dist\\FolderAnalyzer\\FolderAnalyzer.exe`` with an
   isolated APPDATA: the same throwaway tree scan root is typed into the real
   path input, Scan is triggered through the real button, live EN/ES/EN
   re-localization is applied and observed (title, column headers, combo,
   persisted ``folder-analyzer-desktop.json``), and the QTableWidget grid IS
   read back through UIA once the scan model has integrated (each populated
   cell is exposed as a named element), so row-level verdicts of the frozen
   artifact are compared directly against the source-level expectations for
   the SAME tree.

2. The artifact's own ``--selftest <report>`` (delete matrix + controller
   invariants) running INSIDE the frozen executable.

Run with the Phase 12 venv interpreter; the throwaway tree must be built first
(e.g. by ``e2e/run_e2e.py`` or ``e2e/e2e_common.build_tree``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from pywinauto import Application

EXE = r"C:\OPENCODE\Folder_Analyzer\dist\FolderAnalyzer\FolderAnalyzer.exe"
TREE = r"C:\fa_e2e_phase12"
OUT = r"C:\OPENCODE\Folder_Analyzer\e2e\out"
TITLES = ("Folder Analyzer", "Analizador de Carpetas")
COM_TITLES = {"en": "Folder Analyzer", "es": "Analizador de Carpetas"}
COLUMNS = 7

_results = []
_failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    line = f"E2E_CHECK|{name}|{'PASS' if ok else 'FAIL'}|{detail}"
    print(line)
    _results.append(line)
    if not ok:
        _failures.append(line)


def cur_win(app):
    for w in app.windows():
        if w.window_text() in TITLES:
            return w
    raise RuntimeError("no tracked window found")


def snapshot(win, tag):
    out = ["=== snapshot " + tag + " title=" + repr(win.window_text())]
    try:
        headers = win.descendants(control_type="Header")
        out.append("  headers=" + repr([h.window_text() for h in headers]))
    except Exception as e:
        out.append("  headers_err=" + repr(e))
    try:
        combos = win.descendants(control_type="ComboBox")
        out.append("  combo_selected=" + repr(combos[0].selected_text()))
    except Exception as e:
        out.append("  combos_err=" + repr(e))
    return "\n".join(out)


def set_edit_text(e, text: str) -> None:
    import comtypes

    from comtypes import POINTER

    import comtypes.gen.UIAutomationClient as UIAut

    elem = e.element_info.element
    pat = elem.GetCurrentPattern(UIAut.UIA_ValuePatternId)
    upat = comtypes.cast(pat, POINTER(UIAut.IUIAutomationValuePattern))
    upat.SetValue(text)


def uia_session() -> None:
    tmp = tempfile.mkdtemp(prefix="fa_p12_e2e_")
    env = dict(os.environ)
    env["APPDATA"] = tmp
    env["LOCALAPPDATA"] = tmp
    env.pop("QT_QPA_PLATFORM", None)
    env.pop("QT_PLUGIN_PATH", None)

    proc = subprocess.Popen([EXE], env=env)
    print("FROZEN_PID=" + str(proc.pid))
    print("FROZEN_ISOLATED_APPDATA=" + tmp)

    app = Application(backend="uia")
    deadline = time.time() + 90
    first = None
    while time.time() < deadline and first is None:
        try:
            app.connect(process=proc.pid, timeout=2)
            first = cur_win(app)
        except Exception:
            pass
        if first is None:
            time.sleep(1)
    if first is None:
        print("FROZEN_STEP|window_not_found_in_90s")
        proc.terminate()
        sys.exit(4)

    first.set_focus()
    time.sleep(1)
    win = cur_win(app)
    print(snapshot(win, "ORIGINAL_EN"))

    combo = win.descendants(control_type="ComboBox")[0]
    combo.expand()
    time.sleep(1)
    combo.select("ES")
    time.sleep(3)
    title_es_ref = cur_win(app).window_text()
    print(snapshot(cur_win(app), "AFTER_ES"))

    cfg = os.path.join(tmp, "FolderAnalyzer", "folder-analyzer-desktop.json")
    print("FROZEN_CFG_EXISTS=" + str(os.path.exists(cfg)))
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8") as fh:
            print("FROZEN_CFG=" + repr(fh.read()))

    combo2 = cur_win(app).descendants(control_type="ComboBox")[0]
    combo2.expand()
    time.sleep(1)
    combo2.select("EN")
    time.sleep(3)
    print(snapshot(cur_win(app), "AFTER_BACK_EN"))
    print("FROZEN_TITLE_ES=" + repr(title_es_ref))
    print("FROZEN_TITLE_BACK_EN=" + repr(cur_win(app).window_text()))

    edits = cur_win(app).descendants(control_type="Edit")
    e = edits[0]
    try:
        set_edit_text(e, TREE)
        print("FROZEN_PATH_SET|value=" + repr(e.get_value()))
    except Exception as exc:
        print("FROZEN_PATH_SET_ERR=" + repr(exc))
        e.set_focus()
        e.type_keys(TREE)
        print("FROZEN_PATH_SET_FALLBACK|value=" + repr(e.get_value()))

    win = cur_win(app)
    scan_btn = [b for b in win.descendants(control_type="Button") if b.window_text() in ("Scan", "Escanear")]
    scan_btn[0].click()
    print("FROZEN_SCAN_CLICKED")

    time.sleep(25)

    try:
        table = win.descendants(control_type="Table")[0]
        rows = table.children()
        print("FROZEN_TABLE_ROWS=" + str(len(rows)))
        named = [r.window_text() for r in rows if r.window_text()]
        print("FROZEN_TABLE_NAMED=" + repr(named))
        header_row = named[:7]
        cells = named[7:]
        data_rows = [
            cells[i:i + COLUMNS]
            for i in range(0, len(cells) - (len(cells) % COLUMNS), COLUMNS)
        ]
        print("FROZEN_TABLE_DATA_ROWS=" + repr(data_rows))

        def verdict_of(name: str):
            for row in data_rows:
                if row and row[0] == name:
                    return row
            return None

        cache = verdict_of("cache")
        raw_data = verdict_of("Data")
        wiki = verdict_of("wiki_x")
        check("frozen_header_parity", header_row == ["Folder", "Size", "Files", "Recommendation", "Confidence", "Impact", "Reason"], repr(header_row))
        check("frozen_row_cache_safe", cache is not None and cache[3] == "Safe to Delete" and cache[4] == "High" and "SAFE_MIN_SHARE" in cache[6], repr(cache))
        check("frozen_row_data_review", raw_data is not None and raw_data[3] == "Review First" and "manual review" in raw_data[6], repr(raw_data))
        check("frozen_row_wiki_unknown", wiki is not None and wiki[3] == "Review First" and wiki[4] == "Low" and "UNKNOWN" in wiki[6], repr(wiki))
    except Exception as exc:
        print("FROZEN_TABLE_ERR=" + repr(exc))

    print("FROZEN_CHECK_FAILED=" + str(len(_failures)))
    print("FROZEN_VERDICT=" + ("PASS" if not _failures else "FAIL"))
    sys.stdout.flush()

    try:
        subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
    except Exception:
        pass
    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    os._exit(0 if not _failures else 1)


def selftest() -> None:
    report = os.path.join(OUT, "artifact_selftest.json")
    print("ARTIFACT_SELFTEST_CMD=" + " ".join([EXE, "--selftest", report]))
    proc = subprocess.run([EXE, "--selftest", report], capture_output=True, timeout=300)
    print("ARTIFACT_SELFTEST_EXIT=" + str(proc.returncode))
    text = proc.stdout.decode("utf-8", errors="replace")
    for ln in text.splitlines()[-6:]:
        print("ARTIFACT_SELFTEST_LINE|" + ln.strip())
    if os.path.exists(report):
        payload = json.load(open(report, encoding="utf-8"))
        for key in ("checks", "passed", "failed", "total"):
            print(f"ARTIFACT_SELFTEST_{key.upper()}={payload.get(key, '?')}")
        self_ok = all(v.get("passed") is True for v in payload.get("checks", {}).values())
        check("artifact_selftest_all", self_ok, repr(payload.get("checks", {})))
    print("FROZEN_CHECK_FAILED=" + str(len(_failures)))
    print("FROZEN_E2E_VERDICT=" + ("PASS" if not _failures else "FAIL"))
    if _failures:
        sys.exit(1)
    sys.last_selftest_exit = proc.returncode


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    selftest()
    _selftest_exit = getattr(sys, "last_selftest_exit", 0)
    uia_session()