"""Cursor-anchored completion list; focus remains in the editor."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option


class CompletionMenu(Vertical):
    DEFAULT_CSS = """
    CompletionMenu {
        layer: overlay; position: absolute; width: 48; height: auto;
        max-height: 16; background: $panel; border: solid $primary;
    }
    CompletionMenu OptionList { height: auto; max-height: 8; border: none; }
    CompletionMenu Static { height: auto; max-height: 4; padding: 0 1; }
    CompletionMenu Label { height: 1; color: $text-muted; }
    """

    def __init__(self, editor, items: list[dict], snapshot: str, cursor: tuple[int, int]) -> None:
        super().__init__()
        self.editor = editor
        self.items = items
        self.snapshot = snapshot
        self.cursor = cursor

    def compose(self) -> ComposeResult:
        yield OptionList(*(Option(Text(i["label"])) for i in self.items))
        yield Static("", markup=False)
        yield Label("Up/Down select  Tab/Enter insert  Esc close")

    def on_mount(self) -> None:
        self.query_one(OptionList).can_focus = False
        self.query_one(OptionList).highlighted = 0
        offset = self.editor.cursor_screen_offset
        width, height = self.app.size
        self.styles.width = min(48, width)
        self.styles.offset = (max(0, min(offset.x, width - 48)), max(0, min(offset.y + 1, height - 16)))
        self.show_detail()

    def show_detail(self) -> None:
        index = self.query_one(OptionList).highlighted
        if index is not None:
            item = self.items[index]
            self.query_one(Static).update("\n".join(str(item[k]) for k in ("detail", "documentation") if item.get(k)))

    @on(OptionList.OptionHighlighted)
    def highlighted(self) -> None:
        self.show_detail()

    @on(OptionList.OptionSelected)
    def selected(self) -> None:
        self.editor.accept_completion()

    def move(self, delta: int) -> None:
        options = self.query_one(OptionList)
        options.highlighted = ((options.highlighted or 0) + delta) % len(self.items)

    def current_item(self) -> dict:
        return self.items[self.query_one(OptionList).highlighted or 0]
