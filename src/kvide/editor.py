"""The code editor widget: a TextArea bound to a Document model."""

from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea

from .documents import Document


class EditorArea(TextArea):
    """A code-editing TextArea tied to a :class:`~kvide.documents.Document`.

    The document model (``self.doc``) is the durable state; the TextArea is the
    view. Note that ``self.document`` below still refers to Textual's own text
    buffer, not the kvide model.

    ``ctrl+w`` is rebound from Textual's "delete word" to "close this tab";
    delete-word remains available via ``ctrl+backspace``.
    """

    BINDINGS = [Binding("ctrl+w", "close_tab", "Close tab", show=False)]

    class CloseRequested(Message):
        """Posted when Ctrl+W is pressed while this editor is focused."""

    def __init__(self, document: Document, *, id: str | None = None) -> None:
        self.doc = document
        super().__init__(
            document.text,
            language=document.language,
            theme="monokai",
            soft_wrap=False,
            tab_behavior="indent",
            show_line_numbers=True,
            highlight_cursor_line=True,
            id=id,
        )

    @property
    def cursor_position(self) -> tuple[int, int]:
        """1-based (line, column) of the cursor, for the status bar."""
        row, col = self.cursor_location
        return (row + 1, col + 1)

    def action_close_tab(self) -> None:
        self.post_message(self.CloseRequested())

    async def _on_key(self, event: events.Key) -> None:
        """Carry the current line's indentation over to the next line on Enter."""
        if event.key == "enter" and not self.read_only:
            event.stop()
            event.prevent_default()
            start, end = self.selection
            if start != end:
                row, _ = start
                line = self.document[row] if 0 <= row < self.document.line_count else ""
                indent = line[: len(line) - len(line.lstrip())]
                self.replace("\n" + indent, start, end, maintain_selection_offset=False)
            else:
                row, _ = self.cursor_location
                line = self.document[row] if 0 <= row < self.document.line_count else ""
                indent = line[: len(line) - len(line.lstrip())]
                self.insert("\n" + indent)
            return
        await super()._on_key(event)
