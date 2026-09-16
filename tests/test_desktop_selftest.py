"""Mirror of the frozen-artifact self-test, run in-process (Phase 11).

The same ``run_selftest`` routine drives the PyInstaller bundle via
``--selftest <report>``; here it runs against the source tree with the
Recycle Bin short-circuited so the suite never trashes real files.
"""

import json
import os

os.environ.setdefault("FA_SELFTEST_FAKE_TRASH", "1")

from desktop_app.selftest import run_selftest  # noqa: E402


def test_selftest_runs_and_passes(tmp_path):
    report = str(tmp_path / "selftest.json")
    exit_code = run_selftest(report)

    payload = json.loads((tmp_path / "selftest.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["frozen"] is False
    for name, check in payload["checks"].items():
        assert check["passed"], (name, check["detail"])