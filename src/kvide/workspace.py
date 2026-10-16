"""Filesystem and workspace operations.

This module is pure Python: no Textual imports, so it can be tested without a
terminal. All filesystem access from the editor goes through here so that
errors are reported as typed exceptions instead of crashing the UI.
"""

from __future__ import annotations

import os
from pathlib import Path

from .textutil import apply_newlines, detect_newline, normalize_newlines


class WorkspaceError(Exception):
    """Base class for workspace errors."""


class PathNotFound(WorkspaceError):
    """The requested path does not exist."""

    def __init__(self, path: str | Path) -> None:
        self.path = path
        super().__init__(f"path not found: {path}")


class NotADirectory(WorkspaceError):
    """The workspace root is not a directory."""

    def __init__(self, path: str | Path) -> None:
        self.path = path
        super().__init__(f"not a directory: {path}")


class FileReadError(WorkspaceError):
    """A file could not be read."""

    def __init__(self, path: str | Path) -> None:
        self.path = path
        super().__init__(f"cannot read: {path}")


class FileWriteError(WorkspaceError):
    """A file could not be written."""

    def __init__(self, path: str | Path) -> None:
        self.path = path
        super().__init__(f"cannot write: {path}")


# Directories that are never shown in the file tree: they are noise or huge.
IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "node_modules",
    ".eggs",
    "build",
    "dist",
}


def is_hidden_name(name: str) -> bool:
    """True for dot-prefixed entries (hidden on POSIX)."""
    return name.startswith(".")


def is_ignored_dir(name: str) -> bool:
    """True for directories the explorer should always skip."""
    return name in IGNORED_DIRS


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class Workspace:
    """An open project directory and the operations on the files under it."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise PathNotFound(self.root)
        if not self.root.is_dir():
            raise NotADirectory(self.root)

    @property
    def name(self) -> str:
        """Human-readable project name for the header."""
        return self.root.name or str(self.root)

    def read(self, path: str | Path) -> tuple[str, str]:
        """Read a text file, returning ``(lf_normalized_text, newline)``."""
        p = Path(path)
        if not p.exists():
            raise PathNotFound(p)
        try:
            data = p.read_bytes()
        except OSError as exc:
            raise FileReadError(p) from exc
        text = _decode(data)
        newline = detect_newline(text)
        return normalize_newlines(text), newline

    def write(self, path: str | Path, text: str, newline: str = "\n") -> None:
        """Write *text* (LF-normalized) to *path*, preserving *newline*."""
        p = Path(path)
        data = apply_newlines(text, newline).encode("utf-8")
        try:
            p.write_bytes(data)
        except OSError as exc:
            raise FileWriteError(p) from exc

    def walk_files(
        self, *, show_hidden: bool = False, limit: int = 2000
    ) -> list[str]:
        """Return a bounded list of file paths relative to the root.

        Directories in :data:`IGNORED_DIRS` are never entered, and hidden files
        are skipped unless *show_hidden* is true. The scan is depth-first and
        stops once *limit* entries have been collected, so a large tree cannot
        block the UI indefinitely.
        """
        results: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(
                d
                for d in dirnames
                if not is_ignored_dir(d) and (show_hidden or not is_hidden_name(d))
            )
            for filename in sorted(filenames):
                if show_hidden or not is_hidden_name(filename):
                    results.append(str(Path(dirpath, filename).relative_to(self.root)))
                    if len(results) >= limit:
                        return results
            if len(results) >= limit:
                return results
        return results
