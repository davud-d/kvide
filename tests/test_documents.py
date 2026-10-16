"""Tests for the document model and store."""

from __future__ import annotations

from pathlib import Path

import pytest

from kvide.documents import DocumentNotOpen, DocumentStore
from kvide.workspace import Workspace


def _store(root: Path) -> DocumentStore:
    return DocumentStore(Workspace(root))


def test_open_loads_text_language_and_state(project: Path) -> None:
    store = _store(project)
    doc = store.open(project / "src" / "a.py")
    assert doc.text == "x = 1\n"
    assert doc.language == "python"
    assert doc.newline == "\n"
    assert not doc.dirty


def test_open_same_path_returns_same_document(project: Path) -> None:
    store = _store(project)
    first = store.open(project / "src" / "a.py")
    second = store.open(project / "src" / "a.py")
    assert first is second
    assert len(store.documents()) == 1


def test_dirty_tracking(project: Path) -> None:
    store = _store(project)
    doc = store.open(project / "src" / "a.py")
    doc.update_text("x = 42\n")
    assert doc.dirty
    doc.mark_saved(doc.text)
    assert not doc.dirty


def test_save_writes_to_disk_and_clears_dirty(project: Path) -> None:
    store = _store(project)
    doc = store.open(project / "src" / "a.py")
    doc.update_text("x = 42\n")
    store.save_key(store.key_of(doc.path))
    assert (project / "src" / "a.py").read_text(encoding="utf-8") == "x = 42\n"
    assert not doc.dirty


def test_close_removes_document(project: Path) -> None:
    store = _store(project)
    doc = store.open(project / "src" / "a.py")
    key = store.key_of(doc.path)
    store.close_key(key)
    assert store.get_key(key) is None
    assert not store.is_open(doc.path)


def test_save_all_persists_dirty_documents(project: Path) -> None:
    store = _store(project)
    a = store.open(project / "src" / "a.py")
    b = store.open(project / "src" / "b.py")
    a.update_text("new a\n")
    b.update_text("new b\n")
    saved = store.save_all()
    assert len(saved) == 2
    assert not a.dirty and not b.dirty
    assert (project / "src" / "a.py").read_text(encoding="utf-8") == "new a\n"


def test_has_dirty(project: Path) -> None:
    store = _store(project)
    assert not store.has_dirty()
    doc = store.open(project / "src" / "a.py")
    doc.update_text("changed\n")
    assert store.has_dirty()


def test_close_unknown_key_raises(project: Path) -> None:
    store = _store(project)
    with pytest.raises(DocumentNotOpen):
        store.close_key("no-such-key")
