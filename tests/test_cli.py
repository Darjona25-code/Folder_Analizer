"""Tests for CLI helper logic (selection mapping and EOF handling)."""

import pytest
from rich.text import Text  # noqa: F401  (import guard for Prompt patch target)

from folder_analyzer.scanner import FolderInfo
from folder_analyzer.__main__ import ask_text, resolve_selection, _UserExit


def _folder(name: str, size: int = 10) -> FolderInfo:
    return FolderInfo(path=f"C:\\test\\{name}", name=name, total_size=size)


def test_resolve_selection_valid():
    folders = [_folder("a", 3), _folder("b", 2), _folder("c", 1)]
    assert resolve_selection("2", folders).name == "b"


def test_resolve_selection_first():
    folders = [_folder("a"), _folder("b")]
    assert resolve_selection("1", folders).name == "a"


def test_resolve_selection_out_of_range():
    folders = [_folder("a"), _folder("b")]
    assert resolve_selection("5", folders) is None
    assert resolve_selection("0", folders) is None


def test_resolve_selection_non_numeric():
    folders = [_folder("a")]
    assert resolve_selection("abc", folders) is None
    assert resolve_selection("1.5", folders) is None


def test_resolve_selection_maps_to_displayed_child():
    """The displayed child list must be the source of truth, not the root list."""
    root_children = [_folder("root_a"), _folder("root_b")]
    child_list = [_folder("nested_one"), _folder("nested_two")]
    assert resolve_selection("2", child_list).name == "nested_two"
    assert resolve_selection("2", child_list) is not root_children[1]


def test_ask_text_raises_controlled_exit_on_eof(monkeypatch):
    from folder_analyzer import __main__ as main_module

    def boom(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(main_module.Prompt, "ask", boom)
    with pytest.raises(_UserExit):
        ask_text(">", default="0")