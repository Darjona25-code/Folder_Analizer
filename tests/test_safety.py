"""Tests for the safety module."""

from folder_analyzer.safety import get_risk_level, is_deletable, get_risk_color, get_risk_label, RiskLevel


def test_critical_system_folder():
    risk = get_risk_level("C:\\Windows\\System32")
    assert risk == RiskLevel.CRITICAL


def test_critical_winsxs():
    risk = get_risk_level("C:\\Windows\\WinSxS")
    assert risk == RiskLevel.CRITICAL


def test_caution_program_files():
    risk = get_risk_level("C:\\Program Files")
    assert risk == RiskLevel.CAUTION


def test_safe_user_folder():
    risk = get_risk_level("C:\\Users\\arjon\\Documents\\myfile.txt")
    assert risk == RiskLevel.SAFE


def test_safe_temp_folder():
    risk = get_risk_level("C:\\Users\\arjon\\AppData\\Local\\Temp")
    assert risk == RiskLevel.SAFE


def test_is_deletable_safe():
    assert is_deletable("C:\\Users\\arjon\\Downloads\\temp") is True


def test_is_deletable_critical():
    assert is_deletable("C:\\Windows\\System32") is False


def test_risk_colors():
    assert get_risk_color(RiskLevel.CRITICAL) == "red"
    assert get_risk_color(RiskLevel.CAUTION) == "yellow"
    assert get_risk_color(RiskLevel.SAFE) == "green"


def test_risk_labels_en():
    assert get_risk_label(RiskLevel.CRITICAL, "en") == "CRITICAL"
    assert get_risk_label(RiskLevel.CAUTION, "en") == "CAUTION"
    assert get_risk_label(RiskLevel.SAFE, "en") == "SAFE"


def test_risk_labels_es():
    assert get_risk_label(RiskLevel.CRITICAL, "es") == "CRITICO"
    assert get_risk_label(RiskLevel.CAUTION, "es") == "PRECAUCION"
    assert get_risk_label(RiskLevel.SAFE, "es") == "SEGURO"
