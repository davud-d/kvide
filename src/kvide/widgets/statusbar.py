"""Bottom status bar: filename, language, dirty marker and cursor."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


class StatusBar(Static):
    """A single-line status bar driven by :meth:`set_status`."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.filename = ""
        self.language = ""
        self.position = ""
        self.modified = False

    def set_status(
        self,
        *,
        filename: str | None = None,
        language: str | None = None,
        position: str | None = None,
        modified: bool | None = None,
    ) -> None:
        if filename is not None:
            self.filename = filename
        if language is not None:
            self.language = language
        if position is not None:
            self.position = position
        if modified is not None:
            self.modified = modified
        self.refresh()

    def render(self) -> Text:
        width = max(self.size.width, 0)
        left = Text()
        if self.filename:
            left.append(self.filename, style="bold")
        else:
            left.append("no file", style="dim")
        if self.language:
            left.append(f"  {self.language}", style="dim")
        if self.modified:
            left.append("  ●", style="yellow")
        right = Text(self.position, style="dim") if self.position else Text()
        pad = width - left.cell_len - right.cell_len
        return Text.assemble(left, " " * max(0, pad), right)
