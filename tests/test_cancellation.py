"""Phase 8 — scan cancellation: partial results, explicit flag, bounded stop.

``Scanner.scan`` accepts a ``ScanCancellation`` token checked at folder
granularity (and at least once every 4096 files inside a folder). A cancelled
scan returns the partial tree with ``scan_result().cancelled == True``; it is
never a silently-complete result and never corrupts the store. The API wires a
token onto ``app.state`` and exposes ``POST /api/scan/cancel``.
"""

import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

from api.main import app
from folder_analyzer.engine.retention import RetentionConfig
from folder_analyzer.scanner import ScanCancellation, Scanner

client = TestClient(app)


@pytest.fixture
def tmp_dir():
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "file1.txt"), "w") as fh:
            fh.write("x" * 100)
        yield tmpdir


def _build_tree(root, n_subdirs=8, n_files=8):
    """root with n_subdirs subdirs each holding n_files .txt files."""
    for s in range(n_subdirs):
        sub = os.path.join(root, "sub%03d" % s)
        os.makedirs(sub)
        for f in range(n_files):
            with open(os.path.join(sub, "file%03d.txt" % f), "w") as fh:
                fh.write("x" * 100)


def test_pre_cancelled_token_returns_empty_partial(scan_sandbox):
    _build_tree(scan_sandbox)
    token = ScanCancellation()
    token.cancel()
    scanner = Scanner(max_workers=8)
    root = scanner.scan(scan_sandbox, cancellation=token)
    assert scanner.cancelled
    assert root.folder_count == 0
    result = scanner.scan_result()
    assert result.cancelled
    assert result.files_analyzed == 0
    assert result.records_retained == 0


def test_cancel_mid_scan_partial_result_is_consistent(scan_sandbox):
    _build_tree(scan_sandbox, n_subdirs=120, n_files=30)  # 3600 files
    total_files = 120 * 30
    token = ScanCancellation()

    start = time.monotonic()
    timer = threading.Timer(0.05, token.cancel)
    timer.start()
    scanner = Scanner(max_workers=8)
    scanner.scan(scan_sandbox, cancellation=token)
    timer.join()
    elapsed = time.monotonic() - start

    assert scanner.cancelled
    result = scanner.scan_result()
    assert result.cancelled
    # Partial: started scanning but did not finish the whole tree.
    assert 0 < result.files_analyzed < total_files
    # Folder-granularity stop: bounded by finishing the in-flight folder(s).
    assert elapsed < 5.0, f"cancellation took {elapsed:.2f}s"
    # No corruption: every aggregation is a fully completed folder.
    assert result.files_analyzed == sum(
        agg.files_analyzed for agg in result.per_folder.values()
    )
    assert result.records_retained <= RetentionConfig().global_budget


def test_cancel_does_not_break_full_scan_when_token_never_fires(scan_sandbox):
    _build_tree(scan_sandbox, n_subdirs=6, n_files=6)
    scanner = Scanner(max_workers=4)
    scanner.scan(scan_sandbox, cancellation=ScanCancellation())
    result = scanner.scan_result()
    assert not result.cancelled
    assert result.files_analyzed == 6 * 6


def test_api_scan_cancel_endpoint(tmp_dir):
    response = client.post("/api/scan", json={"path": tmp_dir})
    assert response.status_code == 200
    token = getattr(app.state, "last_scan_cancellation", None)
    assert token is not None
    assert isinstance(token, ScanCancellation)
    assert token.is_cancelled is False

    response = client.post("/api/scan/cancel")
    assert response.status_code == 200
    assert response.json() == {"cancelled": True}
    assert token.is_cancelled


def test_api_scan_cancel_without_token(tmp_dir, monkeypatch):
    # Fresh server state: no scan performed yet.
    monkeypatch.setattr(app.state, "last_scan_cancellation", None, raising=False)
    response = client.post("/api/scan/cancel")
    assert response.status_code == 400


def test_api_scan_response_surfaces_cancelled(scan_sandbox):
    """Blocker-1: a scan cancelled mid-run must surface ``cancelled: true`` in
    the /api/scan response alongside the partial stats — never a plain,
    complete-looking payload that silently hides the cancellation."""
    import asyncio

    import httpx

    _build_tree(scan_sandbox, n_subdirs=150, n_files=40)  # 6000 files
    total = 150 * 40

    async def _run():
        # Clear any token a previous test left on server state so the poll
        # below waits for THIS scan's fresh token, not a stale one.
        app.state.last_scan_cancellation = None
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            scan_task = asyncio.create_task(
                ac.post("/api/scan", json={"path": scan_sandbox})
            )
            while getattr(app.state, "last_scan_cancellation", None) is None:
                await asyncio.sleep(0.001)
            cancel_resp = await ac.post("/api/scan/cancel")
            scan_resp = await asyncio.wait_for(scan_task, timeout=20)
            return cancel_resp, scan_resp, app.state.last_scan_cancellation

    cancel_resp, scan_resp, token = asyncio.run(_run())
    assert cancel_resp.status_code == 200
    assert cancel_resp.json() == {"cancelled": True}
    assert token.is_cancelled
    assert scan_resp.status_code == 200
    data = scan_resp.json()
    assert data["cancelled"] is True
    assert 0 <= data["stats"]["total_files"] <= total