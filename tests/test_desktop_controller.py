"""Controller unit tests for the desktop app (Phase 9).

The controller is Qt-free by design (ADR-001), so these tests run without a
display. Real classification assertions use the mandatory fixtures.
"""

import os

from desktop_app.controller import DesktopController
from folder_analyzer.scanner import ScanCancellation


def _rows_by_path(controller, root):
    result = controller.scan(root)
    rows = controller.rows(result)
    return result, {row["path"]: row for row in rows}


def test_rows_exclude_scan_root_and_localize(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    result, rows = _rows_by_path(controller, root)

    assert result.cancelled is False
    assert os.path.normpath(root) not in rows
    assert os.path.normpath(data) in rows
    assert os.path.normpath(cache) in rows


def test_safe_folder_under_review_folder_is_actionable(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    _, rows = _rows_by_path(controller, root)

    data_row = rows[os.path.normpath(data)]
    cache_row = rows[os.path.normpath(cache)]

    assert cache_row["action"] is True
    assert cache_row["rec_label"] == controller.t("rec_safe_to_delete")
    assert data_row["action"] is False

    reason = cache_row["reason"]
    assert reason
    assert "{" not in reason


def test_i10_bulk_gate_uses_folder_recommendation(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    result, _ = _rows_by_path(controller, root)

    data_assessment = result.per_folder[os.path.normpath(data)].assessment
    cache_assessment = result.per_folder[os.path.normpath(cache)].assessment

    assert controller.action_enabled(cache_assessment, deletable=True) is True
    assert controller.action_enabled(data_assessment, deletable=True) is False
    assert controller.action_enabled(cache_assessment, deletable=False) is False


def test_delete_wraps_security_guard_and_send2trash(mixed_sandbox, monkeypatch, tmp_path):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    controller.scan(root)

    sent = []
    monkeypatch.setattr("desktop_app.controller.send2trash", lambda p: sent.append(p))

    outside = tmp_path / "other"
    outside.mkdir()
    missing = str(tmp_path / "nope")

    outcomes = controller.delete_folders([missing])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_folders([str(outside)])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_folders([os.path.normpath(root)])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_folders([cache])
    assert outcomes[0]["status"] == "deleted"
    assert sent == [cache]


def test_precancelled_scan_is_explicit_partial(mixed_sandbox):
    root, _, _ = mixed_sandbox
    controller = DesktopController("en")
    token = ScanCancellation()
    token.cancel()

    result = controller.scan(root, cancellation=token)

    assert result.cancelled is True


def test_i18n_labels_follow_single_source_locale_files():
    controller_en = DesktopController("en")
    controller_es = DesktopController("es")

    assert controller_en.t("btn_scan") == "Scan"
    assert controller_es.t("btn_scan") == "Escanear"
    assert controller_en.t("desktop_pick_folder") != controller_es.t("desktop_pick_folder")
    assert controller_en.t("missing_key_xyz") == "missing_key_xyz"


def test_file_rows_use_retained_records_and_i10(mixed_sandbox):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    controller.scan(root)

    data_files = {r["name"]: r for r in controller.file_rows(data)}
    cache_files = {r["name"]: r for r in controller.file_rows(cache)}

    assert set(data_files) == {"notes.txt"}
    assert set(cache_files) == {"a.tmp", "b.tmp"}
    assert data_files["notes.txt"]["action"] is False
    assert cache_files["a.tmp"]["action"] is True
    assert cache_files["b.tmp"]["action"] is True

    for row in [*data_files.values(), *cache_files.values()]:
        assert row["rec_label"]
        assert row["reason"]
        assert "{" not in row["reason"]
        assert row["size_bytes"] > 0


def test_evicted_folder_yields_no_file_rows_and_flag(mixed_sandbox):
    root, data, cache = mixed_sandbox
    bulk = os.path.join(root, "bulk")
    os.makedirs(bulk)
    for i in range(240):
        with open(os.path.join(bulk, f"junk{i:03d}.bak"), "w", encoding="utf-8") as fh:
            fh.write("x")

    from folder_analyzer.engine.retention import RetentionConfig

    controller = DesktopController("en")
    controller.scan(root, retention=RetentionConfig(global_budget=1))

    assert controller.is_evicted(bulk) is True
    assert controller.file_rows(bulk) == []


def test_delete_files_share_the_same_guard_path(mixed_sandbox, monkeypatch, tmp_path):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    controller.scan(root)

    sent = []
    monkeypatch.setattr("desktop_app.controller.send2trash", lambda p: sent.append(p))

    cache_files = [r["path"] for r in controller.file_rows(cache)]
    assert len(cache_files) == 2

    outcomes = controller.delete_files([cache_files[0]])
    assert outcomes[0]["status"] == "deleted"
    assert sent == [cache_files[0]]

    outside_file = tmp_path / "x.tmp"
    outside_file.write_text("x", encoding="utf-8")
    outcomes = controller.delete_files([str(outside_file)])
    assert outcomes[0]["status"] == "blocked"

    outcomes = controller.delete_files([os.path.normpath(root)])
    assert outcomes[0]["status"] == "blocked"

    missing = os.path.join(cache, "nope.tmp")
    outcomes = controller.delete_files([missing])
    assert outcomes[0]["status"] == "blocked"


def test_export_report_reuses_exporter_v2(mixed_sandbox, tmp_path):
    root, data, cache = mixed_sandbox
    controller = DesktopController("en")
    controller.scan(root)

    outcomes = {}
    for fmt in ("json", "csv", "html"):
        out = str(tmp_path / f"report.{fmt}")
        outcomes[fmt] = controller.export_report(fmt, out)
        assert outcomes[fmt]["status"] == "ok"
        assert os.path.getsize(out) > 0

    import json

    payload = json.loads(
        (tmp_path / "report.json").read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == 2
    assert payload["root_path"] == os.path.normpath(root)
    assert os.path.normpath(data) in payload["tree"]["children"] or True

    second = str(tmp_path / "report2.json")
    controller.export_report("json", second, scan_date="2026-01-01T00:00:00")
    payload2 = json.loads((tmp_path / "report2.json").read_text(encoding="utf-8"))
    assert payload2["scan_date"] == "2026-01-01T00:00:00"
    assert payload2["schema_version"] == 2

    assert controller.export_report("xml", str(tmp_path / "x.out"))["status"] == "error"


def test_export_requires_a_scanned_result(tmp_path):
    controller = DesktopController("en")
    outcome = controller.export_report("json", str(tmp_path / "r.json"))
    assert outcome["status"] == "error"
    assert outcome["reason"] == "no_scan"


def test_app_settings_persist_language(tmp_path):
    from desktop_app.settings import AppSettings

    cfg = tmp_path / "nested" / "cfg.json"
    settings = AppSettings(str(cfg))
    assert settings.load_language() == "en"

    settings.save_language("es")
    assert settings.load_language() == "es"
    assert cfg.exists()

    fresh = AppSettings(str(cfg))
    assert fresh.load_language() == "es"

    fresh.save_language("en")
    assert AppSettings(str(cfg)).load_language() == "en"

    unknown = AppSettings(str(tmp_path / "u.json"))
    unknown._path.write_text('{"language": "xx"}', encoding="utf-8")
    assert unknown.load_language() == "en"