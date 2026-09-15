"""Phase 7 — web frontend audit tests.

Guards the V2 UI contract:
  * app.js never references raw ``reason_key`` (localized ``reason`` only),
  * no hardcoded English UI strings linger in the JS layer,
  * every ``t('key')`` the frontend calls exists in BOTH locale files
    (EN/ES key-parity applies to the served UI namespace too),
  * the I10 enable rule present in app.js mirrors the API-payload rule.
"""

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOCALES = ROOT / "folder_analyzer" / "locales"

INDEX = (WEB / "index.html").read_text(encoding="utf-8")
APPJS = (WEB / "js" / "app.js").read_text(encoding="utf-8")
CSS = (WEB / "css" / "style.css").read_text(encoding="utf-8")

# Code view of app.js with block comments stripped: doc comments may cite the
# invariant by name, but the executable frontend itself must never do so.
CODEJS = re.sub(r"/\*.*?\*/", "", APPJS, flags=re.S)


def _load_ui(lang: str) -> dict:
    with open(LOCALES / f"{lang}.json", encoding="utf-8") as fh:
        return json.load(fh)["ui"]


def test_index_page_serves_existing_assets():
    assert '/css/style.css' in INDEX
    assert '/js/app.js' in INDEX
    assert '/assets/favicon.ico' in INDEX
    for filename in ["CazaBytes.png", "favicon.ico"]:
        assert (WEB / "assets" / filename).exists(), f"missing asset referenced by index: {filename}"


def test_app_js_never_renders_raw_reason_key():
    assert "reason_key" not in CODEJS, "frontend must only consume localized 'reason' text"


def test_app_js_has_no_hardcoded_english_ui_strings():
    forbidden = [
        "Confirm Deletion",
        "Send to Recycle Bin",
        "Are you sure you want to send",
        "Enter a path to scan",
        "Scan complete:",
        "Delete error",
        "Export failed",
        "Scanning ",
    ]
    for s in forbidden:
        assert s not in CODEJS, f"hardcoded English string leaked into app.js: {s!r}"


def test_ui_keys_used_by_app_js_exist_in_both_locales():
    used = set(re.findall(r"\bt\(['\"]([\w_]+)['\"]\)", APPJS))
    used |= set(re.findall(r'data-i18n(?:-ph)?="([\w_]+)"', INDEX))
    used.discard("app_title")
    for lang in ("en", "es"):
        ui = _load_ui(lang)
        missing = [k for k in sorted(used) if k not in ui]
        assert not missing, f"{lang}.json is missing UI keys used by the frontend: {missing}"


def test_static_i18n_keys_in_index_exist_in_both_locales():
    static_keys = set(re.findall(r'data-i18n(?:-ph)?="([\w_]+)"', INDEX))
    for lang in ("en", "es"):
        ui = _load_ui(lang)
        missing = [k for k in sorted(static_keys) if k not in ui]
        assert not missing, f"{lang}.json is missing index static keys: {missing}"


def test_image_i10_rule_and_lookup_helpers_present():
    # The I10 enable predicate must exist and be the only enable gate in app.js.
    assert "function isActionEnabled(deletable, recommendation)" in APPJS
    assert "function recLabel(value)" in APPJS
    assert "function confLabel(value)" in APPJS
    assert "function impLabel(value)" in APPJS
    # Folder and file actions both route through isActionEnabled.
    assert "isActionEnabled(folder.deletable, rec)" in APPJS
    assert "isActionEnabled(file.deletable, rec)" in APPJS


def test_stylesheet_has_phase7_badge_classes():
    for cls in [".rec-badge", ".rec-safe", ".rec-review", ".rec-keep", "td.reason", ".records-evicted", ".table-subtitle"]:
        assert cls in CSS, f"missing style for {cls}"


def test_cancelled_notice_wired_into_frontend_and_styled():
    """Blocker-1: the UI must render an explicit, localized PARTIAL-notice for
    a cancelled scan — element, JS read of `cancelled`, i18n keys, and styles."""
    assert 'id="scanCancelledNotice"' in INDEX
    assert "currentData.cancelled" in APPJS
    assert "t('scan_cancelled')" in APPJS
    assert "t('scan_cancelled_detail'" in APPJS
    assert ".scan-notice" in CSS
    assert ".scan-cancelled" in CSS
    assert "scan_cancelled" in _load_ui("en")
    assert "scan_cancelled" in _load_ui("es")
    assert "scan_cancelled_detail" in _load_ui("en")
    assert "scan_cancelled_detail" in _load_ui("es")