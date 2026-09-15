"""Tests for the FastAPI backend."""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "sub1"))
        os.makedirs(os.path.join(tmpdir, "sub2"))

        for name in ["file1.txt", "file2.txt"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("x" * 1000)

        with open(os.path.join(tmpdir, "sub1", "file3.txt"), "w") as f:
            f.write("y" * 500)

        yield tmpdir


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Folder Analyzer" in response.text


def test_scan_folder(tmp_dir):
    response = client.post("/api/scan", json={"path": tmp_dir})
    assert response.status_code == 200
    data = response.json()
    assert "root" in data
    assert "stats" in data
    assert "top_folders" in data
    assert data["stats"]["total_files"] == 3
    assert data["stats"]["total_size"] == 1000 * 2 + 500


def test_scan_invalid_path():
    response = client.post("/api/scan", json={"path": "Z:\\nonexistent"})
    assert response.status_code == 400


def test_get_folders_after_scan(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.get("/api/folders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_folders_no_scan():
    app.state.last_scan_root = None
    response = client.get("/api/folders")
    assert response.status_code == 400


def test_delete_critical_folder_blocked():
    response = client.post("/api/delete", json={"paths": ["C:\\Windows\\System32"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data["blocked"]) == 1
    assert data["total_blocked"] == 1
    assert data["total_deleted"] == 0


def test_delete_safe_folder(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    safe_path = os.path.join(tmp_dir, "sub2")
    response = client.post("/api/delete", json={"paths": [safe_path]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_blocked"] == 0
    assert data["total_deleted"] == 1


def test_delete_nonexistent_folder():
    response = client.post("/api/delete", json={"paths": ["Z:\\nonexistent"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data["deleted"]) == 1
    assert data["deleted"][0]["success"] is False


def test_delete_multiple_mixed(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    safe_path = os.path.join(tmp_dir, "sub1")
    response = client.post("/api/delete", json={
        "paths": [safe_path, "C:\\Windows\\System32", "Z:\\fake"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_blocked"] == 1
    assert len(data["deleted"]) == 2


def test_export_no_scan():
    app.state.last_scan_root = None
    app.state.last_scan_result = None
    response = client.post("/api/export", json={"format": "json"})
    assert response.status_code == 400


def test_export_no_analysis_returns_400(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    app.state.last_scan_result = None
    response = client.post("/api/export", json={"format": "json"})
    assert response.status_code == 400


def test_export_json_v2_schema(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "json"})
    assert response.status_code == 200
    assert response.json()["schema_version"] == 2
    assert response.json()["root_assessment"] is not None
    assert response.json()["tree"]["assessment"] is not None


def test_scan_stores_scan_result(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    assert app.state.last_scan_result is not None
    assert app.state.last_scan_result.root_path == os.path.normpath(tmp_dir)


def test_export_json(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "json"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


def test_export_csv(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "csv"})
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


def test_export_html(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "html"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_export_invalid_format(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "xml"})
    assert response.status_code == 400


def test_stats_after_scan(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_size" in data
    assert "total_files" in data
    assert "total_folders" in data
    assert "scan_path" in data


def test_drives_endpoint():
    response = client.get("/api/drives")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_folder_dict_has_risk_fields(tmp_dir):
    response = client.post("/api/scan", json={"path": tmp_dir})
    data = response.json()
    root = data["root"]
    assert "risk" in root
    assert "risk_color" in root
    assert "deletable" in root
    assert root["risk"] in ("critical", "caution", "safe")


def test_scan_root_not_in_top_folders(tmp_dir):
    response = client.post("/api/scan", json={"path": tmp_dir})
    data = response.json()
    paths = {f["path"] for f in data["top_folders"]}
    assert os.path.normpath(tmp_dir) not in paths


def test_scan_root_cannot_be_deleted(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/delete", json={"paths": [tmp_dir]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_blocked"] == 1
    assert data["total_deleted"] == 0
    assert os.path.exists(tmp_dir)


def test_ancestor_of_scan_root_cannot_be_deleted(tmp_dir):
    client.post("/api/scan", json={"path": os.path.join(tmp_dir, "sub1")})
    response = client.post("/api/delete", json={"paths": [tmp_dir]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_blocked"] == 1
    assert data["total_deleted"] == 0


def test_child_can_be_deleted_after_scan(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    safe_path = os.path.join(tmp_dir, "sub1")
    response = client.post("/api/delete", json={"paths": [safe_path]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_blocked"] == 0
    assert data["total_deleted"] == 1
    assert not os.path.exists(safe_path)


def test_state_reset_after_restart_reports_no_scan(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    app.state.last_scan_root = None
    app.state.last_scan_result = None
    assert client.get("/api/stats").status_code == 400
    assert client.get("/api/folders").status_code == 400
    assert client.post("/api/export", json={"format": "json"}).status_code == 400


def test_state_is_read_from_app_state(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    import api.main as api_main
    assert api_main.app.state.last_scan_root is not None


def test_drives_include_label():
    response = client.get("/api/drives")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(d["label"] for d in data)
    assert all(d["label"].endswith(":\\") for d in data)


def test_export_csv_localized_es(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "csv", "lang": "es"})
    assert response.status_code == 200
    assert "Carpeta" in response.text


def test_export_csv_default_english(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "csv"})
    assert response.status_code == 200
    assert "Folder" in response.text


def test_export_spanish_html(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "html", "lang": "es"})
    assert response.status_code == 200
    assert "Analizador de Carpetas" in response.text


def test_export_invalid_lang_falls_back_to_english(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.post("/api/export", json={"format": "csv", "lang": "xx"})
    assert response.status_code == 200
    assert "Folder" in response.text


def test_top_folders_are_children_not_root(tmp_dir):
    response = client.post("/api/scan", json={"path": tmp_dir})
    data = response.json()
    root = data["root"]
    root_children = {c["path"] for c in root["children"]}
    for top in data["top_folders"]:
        assert top["path"] in root_children or top["path"].startswith(
            os.path.normpath(tmp_dir) + os.sep
        )


# ---------------------------------------------------------------------------
# Phase 7 — v2 contract surfaces served to the Web UI.
# ---------------------------------------------------------------------------

def _scan_data(tmp_dir, lang="en"):
    return client.post("/api/scan", json={"path": tmp_dir}, params={"lang": lang}).json()


def test_scan_response_carries_v2_assessment_and_composition(tmp_dir):
    data = _scan_data(tmp_dir)
    root = data["root"]
    assert root["assessment"] is not None
    assert set(root["assessment"]).issuperset(
        {"recommendation", "confidence", "impact", "reason_key", "reason"}
    )
    assert root["composition"] is not None
    assert root["recursive_total"] == root["total_size"]
    for top in data["top_folders"]:
        assert top["assessment"] is not None
        assert "reason" in top["assessment"]


def test_scan_locale_localizes_reasons(tmp_dir):
    en = _scan_data(tmp_dir, lang="en")
    es = _scan_data(tmp_dir, lang="es")
    en_keys = {a["reason_key"] for a in [en["root"]["assessment"]] + [t["assessment"] for t in en["top_folders"]]}
    es_keys = {a["reason_key"] for a in [es["root"]["assessment"]] + [t["assessment"] for t in es["top_folders"]]}
    assert en_keys and es_keys
    assert en_keys == es_keys
    assert {a["reason"] for a in [en["root"]["assessment"]] + [t["assessment"] for t in en["top_folders"]]} != {
        a["reason"] for a in [es["root"]["assessment"]] + [t["assessment"] for t in es["top_folders"]]
    }


def test_i18n_endpoint_serves_single_source_ui_and_reasons():
    en = client.get("/api/i18n", params={"lang": "en"}).json()
    es = client.get("/api/i18n", params={"lang": "es"}).json()
    assert "ui" in en and "reasons" in en
    assert set(en["ui"]) == set(es["ui"])
    assert set(en["reasons"]) == set(es["reasons"])
    assert "uncertain" in en["reasons"]


def test_folder_files_returns_localized_retained_records(tmp_dir):
    data = _scan_data(tmp_dir)
    sub1 = os.path.join(tmp_dir, "sub1")
    response = client.get("/api/folder/files", params={"path": sub1, "lang": "en"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["evicted"] is False
    assert payload["folder_assessment"] is not None
    assert len(payload["files"]) == 1
    f = payload["files"][0]
    assert f["name"] == "file3.txt"
    assert f["recommendation"] in ("safe_to_delete", "review_first")
    assert f["confidence"] in ("high", "medium", "low")
    assert f["impact"]
    assert f["reason"] and f["reason"] != f["reason_key"]
    assert "{" not in f["reason"]
    assert f["deletable"]


def test_folder_files_empty_folder_not_evicted(tmp_dir):
    _scan_data(tmp_dir)
    response = client.get("/api/folder/files", params={"path": os.path.join(tmp_dir, "sub2")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["evicted"] is False
    assert payload["files"] == []


def test_folder_files_rejects_path_outside_scan_tree(tmp_dir):
    _scan_data(tmp_dir)
    response = client.get("/api/folder/files", params={"path": "C:\\Windows\\System32"})
    assert response.status_code == 400


def test_folder_files_localizes_for_es(tmp_dir):
    _scan_data(tmp_dir, lang="es")
    response = client.get("/api/folder/files", params={"path": os.path.join(tmp_dir, "sub1"), "lang": "es"})
    assert response.status_code == 200
    f = response.json()["files"][0]
    assert f["reason"] != f["reason_key"]
    # es localization differs from the raw en reason text for the same key
    en = client.get("/api/folder/files", params={"path": os.path.join(tmp_dir, "sub1"), "lang": "en"}).json()["files"][0]
    assert f["reason_key"] == en["reason_key"]
    assert f["reason"] != en["reason"]


def test_no_raw_reason_key_leaks_to_ui_surfaces(tmp_dir):
    """Same audit discipline as Phase 6 CSV/HTML checks, applied to API rows:
    any served ``reason`` must be non-raw localized text whose key is registered."""
    reasons = client.get("/api/i18n", params={"lang": "en"}).json()["reasons"]
    data = _scan_data(tmp_dir)
    assessments = [data["root"]["assessment"]] + [t["assessment"] for t in data["top_folders"]]
    files = client.get("/api/folder/files", params={"path": os.path.join(tmp_dir, "sub1")}).json()["files"]
    for a in assessments:
        if not a:
            continue
        assert a["reason_key"] in reasons
        assert a["reason"] and a["reason"].strip() != a["reason_key"]
        assert "{" not in a["reason"]
    for f in files:
        if not f["recommendation"]:
            continue
        assert f["reason_key"] in reasons
        assert f["reason"] and f["reason"] != f["reason_key"]
        assert "{" not in f["reason"]


def test_i10_gating_rule_data_is_served_consistently(tmp_dir):
    """I10 (item-vs-folder authority) must be implementable from served data:
    the folder assessment and every file carry an independent recommendation,
    and the UI's exact enable rule is mirrored here."""
    data = _scan_data(tmp_dir)
    top = data["top_folders"]
    assert top, "fixture must yield at least one top folder"
    assert all("recommendation" in t["assessment"] for t in top)

    files = client.get("/api/folder/files", params={"path": os.path.join(tmp_dir, "sub1")}).json()["files"]
    assert files, "sub1 holds retained records"

    def ui_action_enabled(deletable, recommendation):
        return bool(deletable and recommendation == "safe_to_delete")

    # mirror of app.js isActionEnabled(): independent per-item authority.
    assert ui_action_enabled(True, "safe_to_delete") is True     # file SAFE → actionable
    assert ui_action_enabled(True, "review_first") is False      # folder REVIEW_FIRST → gated
    assert ui_action_enabled(False, "safe_to_delete") is False   # protection guard always wins

    for f in files:
        assert "deletable" in f and "recommendation" in f
    for t in top:
        assert "deletable" in t and "recommendation" in t["assessment"]
