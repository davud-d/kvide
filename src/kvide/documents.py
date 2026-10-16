"""Document model and the store of open documents.

This module is pure Python (no Textual imports): it owns editing state, dirty
tracking and persistence, and is tested without a terminal.
"""

from __future__ import annotations

from pathlib import Path

from . import workspace as ws
from .languages import detect_language


class DocumentNotOpen(Exception):
    """An operation targeted a document that is not open."""


class Document:
    """A single open file: current text, last-saved text and its newline."""

    def __init__(self, path: Path, text: str, newline: str = "\n") -> None:
        self.path = Path(path)
        self.language = detect_language(self.path.name)
        self.newline = newline
        self.text = text
        self.saved_text = text

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def dirty(self) -> bool:
        return self.text != self.saved_text

    def update_text(self, text: str) -> None:
        """Set the current in-memory text (does not clear the saved snapshot)."""
        self.text = text

    def mark_saved(self, text: str) -> None:
        """Record *text* as the persisted content."""
        self.text = text
        self.saved_text = text


class DocumentStore:
    """Tracks open documents, their order and their persisted state."""

    def __init__(self, workspace: ws.Workspace) -> None:
        self.workspace = workspace
        self._docs: dict[str, Document] = {}
        self._order: list[str] = []

    @staticmethod
    def key_of(path: str | Path) -> str:
        return str(Path(path).resolve())

    def is_open(self, path: str | Path) -> bool:
        return self.key_of(path) in self._docs

    def get(self, path: str | Path) -> Document | None:
        return self._docs.get(self.key_of(path))

    def get_key(self, key: str) -> Document | None:
        return self._docs.get(key)

    def documents(self) -> list[Document]:
        """Open documents in open order."""
        return [self._docs[k] for k in self._order]

    def has_dirty(self) -> bool:
        return any(doc.dirty for doc in self.documents())

    def open(self, path: str | Path) -> Document:
        """Open *path* for editing, or return the already-open document."""
        key = self.key_of(path)
        if key in self._docs:
            return self._docs[key]
        text, newline = self.workspace.read(path)
        doc = Document(Path(path).resolve(), text, newline)
        self._docs[key] = doc
        self._order.append(key)
        return doc

    def close_key(self, key: str) -> Document:
        """Close the document with *key* and return it."""
        if key not in self._docs:
            raise DocumentNotOpen(key)
        self._order.remove(key)
        return self._docs.pop(key)

    def save_key(self, key: str) -> None:
        """Write the document's current text to disk and clear its dirty flag."""
        doc = self._docs.get(key)
        if doc is None:
            raise DocumentNotOpen(key)
        self.workspace.write(doc.path, doc.text, doc.newline)
        doc.mark_saved(doc.text)

    def save_all(self) -> list[Document]:
        """Persist every dirty document; return the ones that were written."""
        saved: list[Document] = []
        for doc in self.documents():
            if doc.dirty:
                self.workspace.write(doc.path, doc.text, doc.newline)
                doc.mark_saved(doc.text)
                saved.append(doc)
        return saved
