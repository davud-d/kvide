"""Tests for newline helpers."""

from kvide.textutil import apply_newlines, detect_newline, normalize_newlines


def test_detect_crlf() -> None:
    assert detect_newline("a\r\nb\r\n") == "\r\n"


def test_detect_lf() -> None:
    assert detect_newline("a\nb\n") == "\n"


def test_detect_mixed_prefers_lf() -> None:
    assert detect_newline("a\r\nb\nc") == "\n"


def test_normalize_newlines() -> None:
    assert normalize_newlines("a\r\nb\rc\n") == "a\nb\nc\n"


def test_apply_crlf() -> None:
    assert apply_newlines("a\nb\n", "\r\n") == "a\r\nb\r\n"


def test_apply_lf_is_noop() -> None:
    assert apply_newlines("a\nb\n", "\n") == "a\nb\n"
