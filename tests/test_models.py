"""Regression tests for Pydantic model defaults."""

from api.models import FolderDict, ExportRequest, DiskInfo


def test_folder_dict_children_are_independent():
    a = FolderDict(path=r"C:\a", name="a")
    b = FolderDict(path=r"C:\b", name="b")

    a.children.append(FolderDict(path=r"C:\a\child", name="child"))

    assert len(a.children) == 1
    assert len(b.children) == 0
    assert b.children is not a.children


def test_folder_dict_deep_children_are_independent():
    a = FolderDict(path="root", name="root")
    a.children.append(FolderDict(path="root\\x", name="x"))

    rebuilt = FolderDict.model_validate(a.model_dump())
    repaired = FolderDict(path="new", name="new")

    assert len(rebuilt.children) == 1
    assert len(repaired.children) == 0


def test_export_request_default_lang():
    req = ExportRequest(format="csv")
    assert req.lang == "en"


def test_disk_info_default_label():
    d = DiskInfo(total=1, used=0, free=1, percent=0.0)
    assert d.label == ""