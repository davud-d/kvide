"""The code editor widget: a TextArea bound to a Document model."""

from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea

from .documents import Document
from .completions import CompletionError, completion_range
from .widgets.completion import CompletionMenu


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
        self.completion_menu: CompletionMenu | None = None
        self.suggestion_cursor: tuple[int, int] | None = None
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

    def on_blur(self) -> None:
        self.dismiss_completion()

    def dismiss_completion(self) -> None:
        if self.completion_menu is not None:
            self.completion_menu.remove()
            self.completion_menu = None

    def show_ghost(self, text: str, cursor: tuple[int, int]) -> None:
        """Draw ``text`` after ``cursor``; only its first line fits on the cursor line."""
        self.suggestion = text.split("\n")[0]
        self.suggestion_cursor = cursor

    def edit(self, edit):
        """Keep ghost text only while the typed text follows it (Textual also keeps it on deletions)."""
        follows = bool(self.suggestion and edit.text and self.suggestion.startswith(edit.text))
        result = super().edit(edit)
        if follows:
            self.suggestion_cursor = self.cursor_location
        else:
            self.suggestion = ""
        return result

    def accept_ghost(self) -> None:
        text, self.suggestion = self.suggestion, ""
        self.insert(text)

    def accept_completion(self) -> None:
        menu = self.completion_menu
        if menu is None:
            return
        self.dismiss_completion()
        if self.read_only or self.text != menu.snapshot or self.cursor_location != menu.cursor:
            return
        try:
            item = menu.current_item()
            start, end = completion_range(self.text, item, self.cursor_location)
            self.replace(item.get("insertText", item["label"]), start, end, maintain_selection_offset=False)
        except CompletionError as exc:
            self.notify(str(exc), severity="error", markup=False)

    async def _on_key(self, event: events.Key) -> None:
        """Accept suggestions first, otherwise preserve TextArea editing."""
        if self.suggestion and self.completion_menu is None and event.key in ("tab", "escape"):
            event.stop()
            event.prevent_default()
            if event.key == "tab" and not self.read_only:
                self.accept_ghost()
            else:
                self.suggestion = ""
            return
        if self.completion_menu is not None:
            if event.key in ("up", "down", "enter", "tab", "escape"):
                event.stop()
                event.prevent_default()
                if event.key in ("up", "down"):
                    self.completion_menu.move(-1 if event.key == "up" else 1)
                elif event.key == "escape":
                    self.dismiss_completion()
                else:
                    self.accept_completion()
                return
            self.dismiss_completion()
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
