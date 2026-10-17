"""Modal screens: confirmations and the quick file switcher."""

from __future__ import annotations

from typing import Sequence

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.fuzzy import FuzzySearch
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList
from textual.widgets.option_list import Option

from .workspace import Workspace


class ConfirmScreen(ModalScreen[str]):
    """A modal prompt that dismisses with the id of the chosen option."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, message: str, choices: Sequence[tuple[str, str]]) -> None:
        super().__init__()
        self.message = message
        self.choices = list(choices)

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.message)
            with Horizontal(id="confirm-buttons"):
                for index, (_result, label) in enumerate(self.choices):
                    yield Button(
                        label,
                        id=f"choice-{index}",
                        variant="primary" if index == 0 else "default",
                    )

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        index = int(event.button.id.removeprefix("choice-"))
        self.dismiss(self.choices[index][0])

    def action_cancel(self) -> None:
        self.dismiss("cancel")


class QuickSwitchScreen(ModalScreen[str]):
    """A fuzzy file picker over the workspace (Ctrl+P)."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, workspace: Workspace, *, show_hidden: bool = False) -> None:
        super().__init__()
        self.workspace = workspace
        self.show_hidden = show_hidden
        self._files: list[str] = []
        self._searcher = FuzzySearch()

    def compose(self) -> ComposeResult:
        with Vertical(id="quick-box"):
            yield Input(placeholder="type to filter files", id="quick-input")
            yield OptionList(id="quick-list")

    def on_mount(self) -> None:
        self.query_one("#quick-input", Input).focus()
        self._scan()

    @work(thread=True)
    def _scan(self) -> None:
        files = self.workspace.walk_files(show_hidden=self.show_hidden)
        self.call_from_thread(self._apply_files, files)

    def _apply_files(self, files: list[str]) -> None:
        if not self.is_mounted:
            return
        self._files = files
        self._refresh()

    @on(Input.Changed)
    def _on_input_changed(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        query = self.query_one("#quick-input", Input).value.strip()
        ranked: list[tuple[float, str]] = []
        for path in self._files:
            if not query:
                ranked.append((0.0, path))
                continue
            score, _ = self._searcher.match(query, path)
            if score > 0.0:
                ranked.append((score, path))
        ranked.sort(key=lambda item: (-item[0], item[1].lower()))
        options = [Option(path, id=path) for _score, path in ranked[:100]]
        option_list = self.query_one("#quick-list", OptionList)
        option_list.clear_options()
        option_list.add_options(options)

    @on(Input.Submitted)
    def _on_input_submitted(self) -> None:
        option_list = self.query_one("#quick-list", OptionList)
        if option_list.option_count:
            first = option_list.get_option_at_index(0)
            if first.id is not None:
                self.dismiss(first.id)

    @on(OptionList.OptionSelected)
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is not None:
            self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ContextMenuScreen(ModalScreen[str]):
    """A modal context menu with a list of actions."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, options: Sequence[tuple[str, str]], x: int = 0, y: int = 0) -> None:
        super().__init__()
        self.options = list(options)
        self.x = x
        self.y = y

    def compose(self) -> ComposeResult:
        option_list = OptionList(id="context-menu-list")
        option_list.styles.offset = (self.x, self.y)
        yield option_list

    def on_mount(self) -> None:
        option_list = self.query_one("#context-menu-list", OptionList)
        for action_id, label in self.options:
            option_list.add_option(Option(label, id=action_id))
        option_list.focus()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is not None:
            self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class InputScreen(ModalScreen[str]):
    """A modal prompt for text input with a single field."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, message: str, placeholder: str = "") -> None:
        super().__init__()
        self.message = message
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="input-box"):
            yield Label(self.message)
            yield Input(placeholder=self.placeholder, id="input-field")
            with Horizontal(id="input-buttons"):
                yield Button("OK", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#input-field", Input).focus()

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self) -> None:
        value = self.query_one("#input-field", Input).value.strip()
        if value:
            self.dismiss(value)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        value = self.query_one("#input-field", Input).value.strip()
        if value:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)
