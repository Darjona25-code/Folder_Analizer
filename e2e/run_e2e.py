"""Phase 12 TASK 2 - E2E scripted parity across CLI, Web API and Desktop.

Run from the repo root with the Phase 12 venv interpreter and the script's own
CWD pointing at the repo (imports resolve from the repo tree):

    python e2e/run_e2e.py

Raw evidence is printed to stdout and also saved under ``e2e/out/`` (gitignored).
Flow per surface uses the SAME throwaway tree built by ``e2e_common.build_tree``;
the tree is rebuilt before every surface so each surface scans byte-identical
content. Delete attempts send SAFE items to the Windows Recycle Bin (throwaway
tree) and must be blocked for REVIEW/UNKNOWN items.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, r"C:\OPENCODE\Folder_Analyzer")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = r"C:\OPENCODE\Folder_Analyzer"
TREE = r"C:\fa_e2e_phase12"
OUT = os.path.join(REPO, "e2e", "out")

import e2e_common as common  # noqa: E402

os.makedirs(OUT, exist_ok=True)

_results = []
_failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    line = f"E2E_CHECK|{name}|{'PASS' if ok else 'FAIL'}|{detail}"
    print(line)
    _results.append(line)
    if not ok:
        _failures.append(line)


def sha1(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def run_cli(lang: str, outdir: str, idx_data: str, idx_cache: str) -> subprocess.CompletedProcess:
    lines = [
        "3", "1", f"cli_{lang}",
        "3", "2", f"cli_{lang}",
        "3", "3", f"cli_{lang}",
        "2", f"{idx_data},{idx_cache}",
    ] + ["y"] * 3 + ["4"]
    input_blob = "\n".join(lines) + "\n"
    cmd = [sys.executable, "-m", "folder_analyzer", "--lang", lang, "--path", TREE]
    print(f"E2E_CMD|CLI|{' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        input=input_blob.encode("utf-8"),
        capture_output=True,
        timeout=240,
        cwd=outdir,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    print(f"CLI_{lang.upper()}_EXIT={proc.returncode}")
    for ln in text.splitlines():
        stripped = ln.strip()
        if any(k in stripped for k in ("Deleted", "deleted", "blocked", "BLOCKED", "Recycle", "marked for deletion", "do not exist", "not exist")):
            print(f"CLI_{lang.upper()}_LINE|{stripped}")
    return proc


def run_web() -> None:
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    data_path = os.path.normpath(os.path.join(TREE, "Data"))
    cache_path = os.path.normpath(os.path.join(TREE, "Data", "cache"))

    r = client.post("/api/scan", json={"path": TREE})
    check("web_scan_status", r.status_code == 200, f"status={r.status_code}")
    body = r.json()
    print("WEB_SCAN|" + json.dumps(body["stats"]))
    check(
        "web_scan_root_not_deletable",
        body["root"]["deletable"] is False,
        f"root.deletable={body['root']['deletable']!r}",
    )

    for lang in ("en", "es"):
        j = client.get("/api/i18n", params={"lang": lang})
        check(f"web_i18n_{lang}", j.status_code == 200 and j.json()["lang"] == lang)
        print(f"WEB_I18N_{lang.upper()}|keys_ui={len(j.json()['ui'])} keys_reasons={len(j.json()['reasons'])}")

    exp = client.post("/api/export", json={"format": "json", "lang": "en"})
    check("web_export_json", exp.status_code == 200, f"status={exp.status_code}")
    out_path = os.path.join(OUT, "web.json")
    with open(out_path, "wb") as fh:
        fh.write(exp.content)
    print(f"WEB_EXPORT_JSON|sha1={sha1(out_path)} bytes={len(exp.content)}")

    files = client.get("/api/folder/files", params={"path": cache_path, "lang": "en"})
    fbody = files.json()
    print("WEB_FILES_CACHE|" + json.dumps([(f["name"], f["recommendation"]) for f in fbody["files"]]))
    check("web_files_cache_retained", len(fbody["files"]) == 2, f"files={len(fbody['files'])}")

    dele = client.post("/api/delete", json={"paths": [cache_path]})
    check("web_delete_status", dele.status_code == 200, f"status={dele.status_code}")
    dbody = dele.json()
    print("WEB_DELETE_CACHE|" + json.dumps(dbody))
    check("web_delete_safe_success", dbody["total_deleted"] == 1 and dbody["total_blocked"] == 0,
          f"deleted={dbody['total_deleted']} blocked={dbody['total_blocked']}")
    check("web_delete_cache_site", os.path.exists(cache_path) is False and os.path.exists(os.path.join(TREE, "README.md")))

    dele_root = client.post("/api/delete", json={"paths": [os.path.normpath(TREE)]})
    droot = dele_root.json()
    print("WEB_DELETE_ROOT|" + json.dumps(droot))
    check("web_delete_root_blocked", droot["total_deleted"] == 0 and os.path.normpath(TREE) in droot["blocked"],
          f"deleted={droot['total_deleted']} blocked={droot['blocked']}")
    check("web_delete_onsite", os.path.exists(TREE) and os.path.exists(data_path))


def run_desktop() -> None:
    from PySide6.QtWidgets import QApplication
    from desktop_app.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    cfg = os.path.join(OUT, "desktop_cfg.json")
    window = MainWindow(config_path=cfg)
    window.show()
    app.processEvents()
    data_path = os.path.normpath(os.path.join(TREE, "Data"))
    cache_path = os.path.normpath(os.path.join(TREE, "Data", "cache"))
    try:
        window._path_input.setText(TREE)
        window._start_scan()
        deadline = time.time() + 120
        while window._worker is not None and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        result = window._result
        check("desktop_scan_done", result is not None and result.cancelled is False)

        rows = window.controller.rows(result)
        for row in rows:
            print("DESKTOP_ROW|" + "|".join([
                row["path"], row["rec_label"], row["conf_label"], row["imp_label"], str(row["deletable"])
            ]))
        row_map = {r["path"]: r for r in rows}
        check("desktop_row_cache_safe", row_map[cache_path]["rec_label"] == "Safe to Delete" and row_map[cache_path]["action"] is True,
              repr(row_map[cache_path]))
        check("desktop_row_data_review", row_map[data_path]["rec_label"] == "Review First" and row_map[data_path]["action"] is False,
              repr(row_map[data_path]))

        out_json = os.path.join(OUT, "desktop.json")
        export = window.controller.export_report("json", out_json)
        check("desktop_export_json", export["status"] == "ok", repr(export))

        window._lang_combo.setCurrentIndex(1)
        app.processEvents()
        check("desktop_reloc_es", window.controller.i18n.lang == "es" and window._table.horizontalHeaderItem(0).text() == "Carpeta",
              f"lang={window.controller.i18n.lang} header0={window._table.horizontalHeaderItem(0).text()!r}")
        window._lang_combo.setCurrentIndex(0)
        app.processEvents()
        check("desktop_reloc_back_en", window.controller.i18n.lang == "en" and window._table.horizontalHeaderItem(0).text() == "Folder")

        window.show_drill_down(data_path)
        app.processEvents()
        data_names = [window._file_table.item(i, 0).text() for i in range(window._file_table.rowCount())]
        print("DESKTOP_DRILL_DATA_NAMES|" + repr(data_names))
        check("desktop_drill_data_user", "notes.txt" in data_names, repr(data_names))
        if "notes.txt" in data_names:
            row = data_names.index("notes.txt")
            window._file_table.selectRow(row)
            app.processEvents()
            check("desktop_drill_data_delete_disabled", window._delete_button.isEnabled() is False)

        window.show_drill_down(cache_path)
        app.processEvents()
        check("desktop_drill_cache_rows", window._file_table.rowCount() == 2,
              f"rowCount={window._file_table.rowCount()}")
        a_row = next(i for i in range(2) if window._file_table.item(i, 0).text() == "a.tmp")
        window._file_table.selectRow(a_row)
        app.processEvents()
        check("desktop_drill_cache_delete_enabled", window._delete_button.isEnabled() is True)

        dele = window.controller.delete_folders([cache_path], confirm=None)
        print("DESKTOP_DELETE_CACHE|" + json.dumps(dele))
        check("desktop_delete_safe_success", dele[0]["status"] == "deleted", repr(dele))
        check("desktop_delete_cache_site", os.path.exists(cache_path) is False and os.path.exists(data_path))

        dele_root = window.controller.delete_folders([os.path.normpath(TREE)], confirm=None)
        print("DESKTOP_DELETE_ROOT|" + json.dumps(dele_root))
        check("desktop_delete_root_blocked", dele_root[0]["status"] == "blocked", repr(dele_root))
        check("desktop_root_onsite", os.path.exists(TREE) and os.path.exists(data_path))
    finally:
        window.close()
        window.deleteLater()


def main() -> int:
    common.build_tree(TREE)
    tree, scan_result, _ = common.scan_tree(TREE)
    ranked = common.ranked_paths(tree)
    data_path = os.path.normpath(os.path.join(TREE, "Data"))
    cache_path = os.path.normpath(os.path.join(TREE, "Data", "cache"))
    idx_data = common.index_of(ranked, data_path) + 1
    idx_cache = common.index_of(ranked, cache_path) + 1
    print("E2E_TREE_RANKED|" + "|".join(ranked))
    print(f"E2E_TREE_INDICES|Data={idx_data} cache={idx_cache}")

    snapshot = common.scan_snapshot(scan_result)
    print("E2E_SCAN_SNAPSHOT|" + json.dumps(snapshot, sort_keys=True))
    check("snapshot_cache_safe", snapshot[cache_path]["recommendation"] == "safe_to_delete" and snapshot[cache_path]["confidence"] == "high",
          repr(snapshot[cache_path]))
    check("snapshot_data_review", snapshot[data_path]["recommendation"] == "review_first", repr(snapshot[data_path]))

    common.build_tree(TREE)
    run_cli("en", OUT, idx_data, idx_cache)
    check("cli_en_site_after_delete", os.path.exists(cache_path) is False and os.path.exists(data_path) is False and os.path.exists(TREE))
    cli_en_out = os.path.join(OUT, "cli_en.json")
    check("cli_en_export_created", os.path.exists(cli_en_out))
    if os.path.exists(cli_en_out):
        print("CLI_EN_EXPORT_SHA1|" + sha1(cli_en_out))

    common.build_tree(TREE)
    run_cli("es", OUT, idx_data, idx_cache)
    check("cli_es_site_after_delete", os.path.exists(cache_path) is False and os.path.exists(data_path) is False and os.path.exists(TREE))
    cli_es_out = os.path.join(OUT, "cli_es.json")
    check("cli_es_export_created", os.path.exists(cli_es_out))
    if os.path.exists(cli_es_out):
        print("CLI_ES_EXPORT_SHA1|" + sha1(cli_es_out))

    common.build_tree(TREE)
    run_web()

    common.build_tree(TREE)
    run_desktop()

    cli_snap = common.export_snapshot(os.path.join(OUT, "cli_en.json"))
    web_snap = common.export_snapshot(os.path.join(OUT, "web.json"))
    desk_snap = common.export_snapshot(os.path.join(OUT, "desktop.json"))
    for name, a, b in (
        ("parity_cli_web", cli_snap, web_snap),
        ("parity_cli_desktop", cli_snap, desk_snap),
        ("parity_web_desktop", web_snap, desk_snap),
    ):
        equal = a == b
        check(name, equal, "" if equal else f"diff keys={set(a) ^ set(b)}")

    print("\n=== E2E RAW REPORT SUMMARY ===")
    print("checks_run=" + str(len(_results)))
    print("checks_failed=" + str(len(_failures)))
    for f in _failures:
        print("FAILED|" + f)
    print("E2E_SURFACES_VERDICT=" + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())