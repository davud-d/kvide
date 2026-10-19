"""Completion extension processes and UTF-16 positions (pure Python)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


# Inline providers usually call a model, which takes longer than a list lookup.
INLINE_TIMEOUT_SECONDS = 15


class CompletionError(Exception):
    """An extension failed, timed out, or returned invalid data."""


def utf16_column(line: str, column: int) -> int:
    return len(line[:column].encode("utf-16-le")) // 2


def python_column(line: str, column: int) -> int:
    if not isinstance(column, int) or column < 0:
        raise CompletionError("Invalid completion column")
    for index in range(len(line) + 1):
        if utf16_column(line, index) == column:
            return index
    raise CompletionError("Completion position is outside the document or splits a surrogate pair")


def completion_range(text: str, item: dict, cursor: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Validate a replacement range before changing any buffer content."""
    lines = text.split("\n")
    raw = item.get("range")
    if raw is None:
        row, col = cursor
        start = col
        while start and (lines[row][start - 1].isalnum() or lines[row][start - 1] == "_"):
            start -= 1
        return (row, start), cursor
    try:
        positions = []
        for point in (raw["start"], raw["end"]):
            row = point["line"]
            if not isinstance(row, int) or not 0 <= row < len(lines):
                raise CompletionError("Invalid completion line")
            positions.append((row, python_column(lines[row], point["character"])))
        start, end = positions
        if start > end or not start <= cursor <= end or start[0] != end[0]:
            raise CompletionError("Completion range must contain the cursor on one line")
        return start, end
    except (KeyError, TypeError, ValueError) as exc:
        raise CompletionError("Invalid completion range") from exc


class ExtensionHost:
    """One explicitly trusted Node extension, serialized requests, bounded lifetime."""

    def __init__(self, extension: Path, root: Path) -> None:
        self.extension = extension.resolve()
        self.root = root
        self.process: asyncio.subprocess.Process | None = None
        self.lock = asyncio.Lock()
        self.request_id = 0

    async def complete(self, request: dict, timeout: float = 5) -> list[dict]:
        async with self.lock:
            try:
                async with asyncio.timeout(timeout):
                    if self.process is None:
                        self.process = await asyncio.create_subprocess_exec(
                            "node", str(Path(__file__).with_name("completion_host.cjs")),
                            str(self.extension), str(self.root), cwd=self.root,
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL, limit=2 * 1024 * 1024,
                        )
                    self.request_id += 1
                    payload = {**request, "id": self.request_id, "version": self.request_id}
                    self.process.stdin.write((json.dumps(payload) + "\n").encode())
                    await self.process.stdin.drain()
                    while True:
                        result = json.loads(await self.process.stdout.readline())
                        # A cancelled request leaves its answer in the pipe; skip it.
                        if not isinstance(result, dict) or not isinstance(result.get("id"), int) \
                                or result["id"] >= self.request_id:
                            break
                    if not isinstance(result, dict):
                        raise CompletionError("Extension returned an invalid response object")
                    if result.get("id") != self.request_id:
                        raise CompletionError("Extension returned an unexpected response id")
                    if result.get("error"):
                        raise CompletionError(str(result["error"]))
                    items = result.get("items")
                    key = "insertText" if request.get("inline") else "label"
                    if not isinstance(items, list) or any(
                        not isinstance(i, dict) or not isinstance(i.get(key), str)
                        or not isinstance(i.get("insertText", i.get("label")), str) for i in items
                    ):
                        raise CompletionError("Extension returned invalid completion items")
                    return items[:100]
            except asyncio.CancelledError:
                raise  # the process stays up: a cold start costs more than the stale answer
            except (OSError, ValueError, TypeError, TimeoutError, CompletionError) as exc:
                await self.close()
                raise CompletionError(f"{self.extension.name}: {exc or 'extension timed out'}") from exc

    async def close(self) -> None:
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()


class CompletionService:
    """Merge results from explicitly enabled extension directories."""

    def __init__(self, extensions: list[Path], root: Path) -> None:
        self.hosts = [ExtensionHost(path, root) for path in extensions]

    def _request(self, path: Path, language: str, text: str, cursor: tuple[int, int], trigger: str | None) -> dict:
        row, col = cursor
        return {
            "path": str(path), "languageId": {
                ".ts": "typescript", ".tsx": "typescriptreact", ".jsx": "javascriptreact",
                ".sh": "shellscript", ".bash": "shellscript",
            }.get(path.suffix.lower(), language), "text": text,
            "position": {"line": row, "character": utf16_column(text.split("\n")[row], col)},
            "triggerKind": 0 if trigger is None else 1, "triggerCharacter": trigger,
        }

    async def complete(self, path: Path, language: str, text: str, cursor: tuple[int, int], trigger: str | None = None) -> list[dict]:
        request = self._request(path, language, text, cursor, trigger)
        items = []
        for host in self.hosts:
            items.extend(await host.complete(request))
        return sorted(items, key=lambda i: i.get("sortText") or i["label"])[:100]

    async def inline(self, path: Path, language: str, text: str, cursor: tuple[int, int], automatic: bool) -> str:
        """The text to show after the cursor as ghost text, or "" when no host offers any.

        Only an item whose range text is a prefix of its ``insertText`` can be
        drawn after the cursor; others are skipped.
        """
        request = {**self._request(path, language, text, cursor, None), "inline": True,
                   "triggerKind": 1 if automatic else 0}
        for host in self.hosts:
            for item in await host.complete(request, timeout=INLINE_TIMEOUT_SECONDS):
                start, end = completion_range(text, item, cursor)
                if end != cursor:
                    continue
                replaced = text.split("\n")[start[0]][start[1]:end[1]]
                insert = item["insertText"]
                if insert.startswith(replaced) and insert[len(replaced):]:
                    return insert[len(replaced):]
        return ""

    async def close(self) -> None:
        for host in self.hosts:
            await host.close()
