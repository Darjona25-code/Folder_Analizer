"""Tests for CLI helper logic (selection mapping and EOF handling)."""

import pytest
from rich.text import Text  # noqa: F401  (import guard for Prompt patch target)

from folder_analyzer.scanner import FolderInfo, ScanCancellation
from folder_analyzer.__main__ import ask_text, resolve_selection, _UserExit, do_scan
from folder_analyzer.i18n import I18n


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
        main_module.ask_text("nope")


def test_cancelled_scan_is_announced_as_partial_not_complete():
    """A cancelled scan must be announced with the PARTIAL marker and must NOT
    use the success framing of a complete scan (charter constraint #3)."""
    import os
    import tempfile
    from io import StringIO

    from rich.console import Console

    with tempfile.TemporaryDirectory() as tmpdir:
        for s in range(4):
            sub = os.path.join(tmpdir, "sub%02d" % s)
            os.makedirs(sub)
            for f in range(5):
                with open(os.path.join(sub, "f%02d.txt" % f), "w") as fh:
                    fh.write("x" * 100)

        i18n = I18n("en")
        token = ScanCancellation()
        token.cancel()
        buffer = StringIO()
        console = Console(file=buffer)
        root, scan_result = do_scan(tmpdir, i18n, console, cancellation=token)
        out = buffer.getvalue()

        assert scan_result.cancelled is True
        assert root.folder_count == 0          # pre-cancelled: empty partial
        assert i18n.t("scan_cancelled") in out
        assert "0 B" in out                     # size interpolated into detail
        assert "{size}" not in out and "{count}" not in out
        assert i18n.t("scan_complete") not in out