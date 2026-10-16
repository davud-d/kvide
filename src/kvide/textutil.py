"""Newline and small text helpers, kept free of any UI dependency."""

from __future__ import annotations


def detect_newline(text: str) -> str:
    """Return the dominant line ending of *text*: ``"\\r\\n"`` or ``"\\n"``."""
    if "\r\n" in text:
        # Prefer CRLF only when every newline is a CRLF pair.
        if text.count("\n") == text.count("\r\n"):
            return "\r\n"
    return "\n"


def normalize_newlines(text: str) -> str:
    """Fold CRLF and lone CR into LF so the editor sees a single form."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def apply_newlines(text: str, newline: str) -> str:
    """Apply *newline* to an LF-normalized string."""
    if newline == "\r\n":
        return text.replace("\n", "\r\n")
    return text
