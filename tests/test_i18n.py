"""Tests for the i18n module."""

from folder_analyzer.i18n import I18n


def test_default_english():
    i18n = I18n()
    assert i18n.t("app_title") == "Folder Analyzer"
    assert i18n.lang == "en"


def test_spanish():
    i18n = I18n("es")
    assert i18n.t("app_title") == "Analizador de Carpetas"
    assert i18n.lang == "es"


def test_format_string():
    i18n = I18n("en")
    result = i18n.t("scan_complete")
    assert isinstance(result, str)
    assert len(result) > 0


def test_format_with_kwargs():
    i18n = I18n("en")
    result = i18n.t("scan_error", path="C:\\test", error="not found")
    assert "C:\\test" in result
    assert "not found" in result


def test_format_with_kwargs_es():
    i18n = I18n("es")
    result = i18n.t("scan_error", path="C:\\test", error="no encontrado")
    assert "C:\\test" in result


def test_set_lang():
    i18n = I18n("en")
    assert i18n.lang == "en"
    i18n.set_lang("es")
    assert i18n.lang == "es"
    assert i18n.t("app_title") == "Analizador de Carpetas"


def test_invalid_lang_fallback():
    i18n = I18n("fr")
    assert i18n.lang == "en"


def test_invalid_lang_set():
    i18n = I18n("en")
    i18n.set_lang("fr")
    assert i18n.lang == "en"


def test_unknown_key():
    i18n = I18n("en")
    result = i18n.t("nonexistent_key")
    assert result == "nonexistent_key"


def test_all_keys_exist_en():
    i18n = I18n("en")
    keys = [
        "app_title", "scan_path_prompt", "scanning", "scan_complete",
        "top_folders", "menu_details", "menu_delete", "menu_export",
        "menu_quit", "delete_confirm", "export_json", "export_csv",
        "export_html", "goodbye", "tagline", "delete_prompt_hint",
        "delete_root_blocked", "delete_warning_program", "deleted_count",
        "col_subfolders", "col_distribution", "files_count", "folders_count",
        "export_csv_size_bytes", "export_csv_size_human",
    ]
    for key in keys:
        result = i18n.t(key)
        assert result != key, f"Key '{key}' not found in English translations"


def test_all_keys_exist_es():
    i18n = I18n("es")
    keys = [
        "app_title", "scan_path_prompt", "scanning", "scan_complete",
        "top_folders", "menu_details", "menu_delete", "menu_export",
        "menu_quit", "delete_confirm", "export_json", "export_csv",
        "export_html", "goodbye", "tagline", "delete_prompt_hint",
        "delete_root_blocked", "delete_warning_program", "deleted_count",
        "col_subfolders", "col_distribution", "files_count", "folders_count",
        "export_csv_size_bytes", "export_csv_size_human",
    ]
    for key in keys:
        result = i18n.t(key)
        assert result != key, f"Key '{key}' not found in Spanish translations"
