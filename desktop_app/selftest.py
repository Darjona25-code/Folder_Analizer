"""Self-test for the frozen desktop artifact (Phase 11).

Run as ``FolderAnalyzer.exe --selftest <report.json>`` (or
``python -m desktop_app --selftest <path>``). Controller-level verification,
Qt-free, mirroring the committed desktop tests: package version, bundled
locales (loaded from inside the bundle, key parity, string resolution), scan
completion, the I10 folder/file gates, and the six-condition guarded delete
(blocked / cancelled / deleted) against a throwaway sandbox created under the
user profile. Writes a JSON report and returns exit code 0/1.

The frozen run exercises the real ``send2trash`` backend; the in-repo pytest
mirror sets ``FA_SELFTEST_FAKE_TRASH=1`` so the suite never touches the
Recycle Bin.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_PREFIX = ".fa_p11_selftest_"

_NEUTRAL_ENV = {
    "TEMP": "C:\\fa_neutral\\temp",
    "TMP": "C:\\fa_neutral\\temp",
    "LOCALAPPDATA": "C:\\fa_neutral\\localappdata",
    "APPDATA": "C:\\fa_neutral\\roaming",
    "USERPROFILE": "C:\\fa_neutral\\profile",
    "PROGRAMDATA": "C:\\fa_neutral\\programdata",
    "PROGRAMFILES": "C:\\fa_neutral\\programfiles",
    "PROGRAMFILES(X86)": "C:\\fa_neutral\\programfiles_x86",
}


def _neutralize_classification():
    """Mirror tests/conftest.py ``classification_neutral_env`` so the real
    machine environment cannot reclassify the throwaway sandbox."""
    import folder_analyzer.engine.kb.env_paths as env_paths
    from folder_analyzer.engine.kb import reset_session_caches

    saved_env = {key: os.environ.get(key) for key in _NEUTRAL_ENV}
    state = (env_paths, reset_session_caches, env_paths._known_folder_path)
    os.environ.update(_NEUTRAL_ENV)
    env_paths._known_folder_path = lambda _key: None
    reset_session_caches()
    return saved_env, state


def _restore_classification(saved_env, state):
    import os

    env_paths, reset_session_caches, orig_lookup = state
    for key, value in saved_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    env_paths._known_folder_path = orig_lookup
    reset_session_caches()


def _build_sandbox(base: str) -> tuple[str, str, str]:
    root = Path(base) / (_PREFIX + str(int(time.time() * 1000)))
    data = root / "Data"
    cache = data / "cache"
    cache.mkdir(parents=True)
    (data / "notes.txt").write_text("hello", encoding="utf-8")
    (cache / "a.tmp").write_text("tmp")
    (cache / "b.tmp").write_text("tmp")
    return str(root), str(data), str(cache)


def run_selftest(report_path: str) -> int:
    import folder_analyzer
    import desktop_app.controller as controller_mod
    from folder_analyzer.i18n import I18n, REASONS, STRINGS

    report: dict = {
        "phase": "11",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "checks": {},
    }
    ok = True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        report["checks"][name] = {"passed": bool(passed), "detail": detail}
        ok = ok and bool(passed)

    version = getattr(folder_analyzer, "__version__", None)
    check("version_300", version == "3.0.0", str(version))

    en = STRINGS.get("en", {})
    es = STRINGS.get("es", {})
    check(
        "locales_bundled",
        bool(en)
        and bool(es)
        and bool(REASONS.get("en"))
        and bool(REASONS.get("es")),
        (
            f"ui en={len(en)} es={len(es)} "
            f"reasons en={len(REASONS.get('en', {}))} es={len(REASONS.get('es', {}))}"
        ),
    )
    check(
        "locales_key_parity",
        set(en) == set(es),
        f"en keys={len(en)} es keys={len(es)}",
    )
    en_text = I18n("en").t("col_name")
    es_text = I18n("es").t("col_name")
    check(
        "locales_resolve",
        en_text != "col_name" and es_text != "col_name",
        f"en col_name={en_text!r} es col_name={es_text!r}",
    )

    base = os.environ.get("USERPROFILE") or tempfile.gettempdir()
    root, data, cache = _build_sandbox(base)

    fake_trash = os.environ.get("FA_SELFTEST_FAKE_TRASH", "0") == "1"
    trashed: list[str] = []

    def _record_trash(path) -> None:
        trashed.append(path)

    if fake_trash:
        controller_mod.send2trash = _record_trash

    DesktopController = controller_mod.DesktopController
    saved_env, state = _neutralize_classification()
    try:
        controller = DesktopController("en")
        result = controller.scan(root)
        check(
            "scan_completes",
            result is not None and result.cancelled is False,
            f"cancelled={'yes' if result and result.cancelled else 'no'}",
        )

        rows = {r["path"]: r for r in controller.rows(result)}
        cache_row = rows.get(os.path.normpath(cache))
        data_row = rows.get(os.path.normpath(data))
        check(
            "i10_folder_gate",
            cache_row is not None
            and data_row is not None
            and cache_row["action"] is True
            and data_row["action"] is False,
            (
                f"cache.action={cache_row and cache_row['action']} "
                f"data.action={data_row and data_row['action']}"
            ),
        )

        files_data = {r["name"]: r for r in controller.file_rows(data)}
        files_cache = {r["name"]: r for r in controller.file_rows(cache)}
        i10_files_ok = (
            set(files_data) == {"notes.txt"}
            and set(files_cache) == {"a.tmp", "b.tmp"}
            and files_data["notes.txt"]["action"] is False
            and files_cache["a.tmp"]["action"] is True
            and files_cache["b.tmp"]["action"] is True
        )
        check(
            "i10_file_gate",
            i10_files_ok,
            f"data={sorted(files_data)} cache={sorted(files_cache)}",
        )

        missing = os.path.join(cache, "no_such.tmp")
        outside = Path(base) / (".fa_p11_outside_" + str(int(time.time() * 1000)) + ".tmp")
        outside.write_text("x", encoding="utf-8")
        try:
            outcomes = controller.delete_files(
                [missing, str(outside), os.path.normpath(root)]
            )
            statuses = [o["status"] for o in outcomes]
            check("guard_blocks_invalid_targets", statuses == ["blocked", "blocked", "blocked"], str(statuses))

            cancelled_marker = os.path.join(cache, "cancel.tmp")
            with open(cancelled_marker, "w", encoding="utf-8") as fh:
                fh.write("tmp")
            cancelled = controller.delete_files(
                [cancelled_marker], confirm=lambda path: False
            )[0]
            check(
                "guard_confirm_cancel",
                cancelled["status"] == "cancelled" and os.path.exists(cancelled_marker),
                f"status={cancelled['status']} remains={os.path.exists(cancelled_marker)}",
            )

            deleted_marker = os.path.join(cache, "delete.tmp")
            with open(deleted_marker, "w", encoding="utf-8") as fh:
                fh.write("tmp")
            deleted = controller.delete_files([deleted_marker])[0]
            gone = not os.path.exists(deleted_marker)
            check(
                "guard_send2trash_deletes",
                deleted["status"] == "deleted" and (fake_trash or gone),
                (
                    f"status={deleted['status']} removed_from_fs={gone} "
                    f"backend={'fake' if fake_trash else 'real_send2trash'}"
                ),
            )
            if fake_trash:
                check("fake_trash_recorded", trashed == [deleted_marker], str(trashed))
        finally:
            outside.unlink(missing_ok=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
        _restore_classification(saved_env, state)

    report["passed"] = ok
    out = Path(report_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if ok else 1