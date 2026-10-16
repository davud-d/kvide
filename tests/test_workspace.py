"""Tests for workspace/filesystem operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from kvide.workspace import (
    NotADirectory,
    PathNotFound,
    Workspace,
)


def test_read_lf(project: Path) -> None:
    ws = Workspace(project)
    text, newline = ws.read(project / "src" / "a.py")
    assert text == "x = 1\n"
    assert newline == "\n"


def test_read_crlf_is_normalized_and_detected(tmp_path: Path) -> None:
    f = tmp_path / "c.py"
    f.write_bytes(b"a = 1\r\nb = 2\r\n")
    ws = Workspace(tmp_path)
    text, newline = ws.read(f)
    assert newline == "\r\n"
    assert text == "a = 1\nb = 2\n"


def test_read_unicode_filename_with_spaces(project: Path) -> None:
    ws = Workspace(project)
    f = project / "файл с пробелами.py"
    f.write_text("print('hi')\n", encoding="utf-8")
    text, _ = ws.read(f)
    assert text == "print('hi')\n"


def test_write_preserves_crlf(tmp_path: Path) -> None:
    f = tmp_path / "c.py"
    ws = Workspace(tmp_path)
    ws.write(f, "a = 1\nb = 2\n", newline="\r\n")
    assert f.read_bytes() == b"a = 1\r\nb = 2\r\n"


def test_read_missing_raises(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    with pytest.raises(PathNotFound):
        ws.read(tmp_path / "nope.py")


def test_root_must_be_directory(tmp_path: Path) -> None:
    f = tmp_path / "f.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectory):
        Workspace(f)


def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(PathNotFound):
        Workspace(tmp_path / "does-not-exist")


def test_walk_files_skips_ignored_and_hidden(project: Path) -> None:
    ws = Workspace(project)
    files = ws.walk_files()
    assert "src/a.py" in files
    assert ".hidden" not in files
    assert not any("node_modules" in p for p in files)


def test_walk_files_show_hidden(project: Path) -> None:
    ws = Workspace(project)
    files = ws.walk_files(show_hidden=True)
    assert ".hidden" in files
    assert not any("node_modules" in p for p in files)
