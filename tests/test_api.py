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
        os.makedirs(os.path.join(tmpdir, "sub1", "deep"))

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
    from api import routes
    routes._last_scan_root = None
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
    safe_path = os.path.join(tmp_dir, "sub1")
    response = client.post("/api/delete", json={
        "paths": [safe_path, "C:\\Windows\\System32", "Z:\\fake"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_blocked"] == 1
    assert len(data["deleted"]) == 2


def test_export_no_scan():
    from api import routes
    routes._last_scan_root = None
    response = client.post("/api/export", json={"format": "json"})
    assert response.status_code == 400


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


# ======================== FOLDER DETAIL TESTS ========================


def test_folder_detail_valid(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    sub1_path = os.path.join(tmp_dir, "sub1")
    response = client.get(f"/api/folder/detail?path={sub1_path}")
    assert response.status_code == 200
    data = response.json()
    assert "folder" in data
    assert "children" in data
    assert "safe_count" in data
    assert "caution_count" in data
    assert "critical_count" in data
    assert data["folder"]["name"] == "sub1"
    assert len(data["children"]) == 1
    assert data["children"][0]["name"] == "deep"


def test_folder_detail_root(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.get(f"/api/folder/detail?path={tmp_dir}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["children"]) == 2
    child_names = {c["name"] for c in data["children"]}
    assert "sub1" in child_names
    assert "sub2" in child_names


def test_folder_detail_not_found(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.get("/api/folder/detail?path=Z:\\nonexistent")
    assert response.status_code == 404


def test_folder_detail_no_scan():
    from api import routes
    routes._last_scan_root = None
    response = client.get("/api/folder/detail?path=C:\\")
    assert response.status_code == 400


def test_folder_detail_leaf_folder(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    deep_path = os.path.join(tmp_dir, "sub1", "deep")
    response = client.get(f"/api/folder/detail?path={deep_path}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["children"]) == 0


def test_folder_detail_risk_counts(tmp_dir):
    client.post("/api/scan", json={"path": tmp_dir})
    response = client.get(f"/api/folder/detail?path={tmp_dir}")
    assert response.status_code == 200
    data = response.json()
    total = data["safe_count"] + data["caution_count"] + data["critical_count"]
    assert total == len(data["children"])
