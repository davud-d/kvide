"""The kvide application: lifecycle, wiring and commands."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button

from .generators import GeneratorError, load_generators
from .git import GitRepository
from .widgets.commit import CommitPanel
from textual.events import Click
from textual.widgets import DirectoryTree, Footer, TabbedContent, TabPane, TextArea

from . import workspace as ws
from .config import Settings
from .documents import Document, DocumentStore
from .editor import EditorArea
from .screens import ConfirmScreen, QuickSwitchScreen
from .theme import APP_CSS
from .widgets import ProjectExplorer, ProjectHeader, StatusBar


class KvideApp(App):
    """The terminal IDE application."""

    TITLE = "kvide"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+w", "close_tab", "Close tab"),
        Binding("ctrl+tab", "next_tab", "Next tab"),
        Binding("ctrl+shift+tab", "prev_tab", "Previous tab"),
        Binding("ctrl+pagedown", "next_tab", "Next tab", show=False),
        Binding("ctrl+pageup", "prev_tab", "Previous tab", show=False),
        Binding("ctrl+p", "quick_switch", "Quick switch"),
        Binding("ctrl+b", "show_files", "Files"),
        Binding("ctrl+g", "show_commit", "Commit"),
    ]

    def __init__(self, workspace: ws.Workspace, settings: Settings) -> None:
        super().__init__()
        self.workspace = workspace
        self.settings = settings
        self.store = DocumentStore(workspace)
        self.generators = []
        self.generator_error = None
        if settings.generators_config is not None:
            try:
                self.generators = load_generators(workspace, Path(settings.generators_config).resolve())
            except GeneratorError as exc:
                self.generator_error = str(exc)

        # UI bookkeeping: document key <-> pane/editor ids.
        self._pane_id: dict[str, str] = {}
        self._doc_key: dict[str, str] = {}
        self._key_editor: dict[str, str] = {}
        self._editor_key: dict[str, str] = {}
        self._editors: dict[str, EditorArea] = {}
        self._id_counter = 0

    # -- composition ---------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield ProjectHeader(self.workspace.name, id="header")
        with Horizontal(id="body"):
            with Vertical(id="activity-bar"):
                files_button = Button('\uf07c' if self.settings.icon_mode == 'nerd' else 'F', id='show-files', classes='active')
                files_button.tooltip = 'Files (Ctrl+B)'
                yield files_button
                commit_button = Button('\ue729' if self.settings.icon_mode == 'nerd' else 'G', id='show-commit')
                commit_button.tooltip = 'Commit (Ctrl+G)'
                yield commit_button
            yield CommitPanel(GitRepository(self.workspace), self.generators, self.settings.icon_mode)
            yield ProjectExplorer(
                str(self.workspace.root),
                icon_mode=self.settings.icon_mode,
                show_hidden=self.settings.show_hidden,
                id="explorer",
            )
            yield TabbedContent(id="tabs")
        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.tabs = self.query_one("#tabs", TabbedContent)
        self.status = self.query_one("#status", StatusBar)
        self.query_one(ProjectExplorer).focus()
        self.query_one(CommitPanel).display = False
        if self.generator_error:
            self.notify(self.generator_error, severity='error', markup=False)
        self._refresh_status()

    @on(Button.Pressed, '#show-files')
    def action_show_files(self) -> None:
        self.query_one(CommitPanel).display = False
        self.query_one(ProjectExplorer).display = True
        self.query_one('#show-files').add_class('active')
        self.query_one('#show-commit').remove_class('active')
        self.query_one(ProjectExplorer).focus()

    @on(Button.Pressed, '#show-commit')
    def action_show_commit(self) -> None:
        self.query_one(ProjectExplorer).display = False
        panel = self.query_one(CommitPanel)
        panel.display = True
        self.query_one('#show-files').remove_class('active')
        self.query_one('#show-commit').add_class('active')
        panel.query_one('#commit-files').focus()
        panel.refresh_changes()

    # -- helpers -------------------------------------------------------------

    def current_key(self) -> str | None:
        return self._doc_key.get(self.tabs.active)

    def current_doc(self) -> Document | None:
        key = self.current_key()
        return None if key is None else self.store.get_key(key)

    def current_editor(self) -> EditorArea | None:
        key = self.current_key()
        editor_id = self._key_editor.get(key) if key else None
        return self._editors.get(editor_id) if editor_id else None

    def _tab_label(self, doc: Document) -> str:
        return f"● {doc.name}" if doc.dirty else doc.name

    def _update_tab_label(self, doc: Document) -> None:
        pane_id = self._pane_id.get(self.store.key_of(doc.path))
        if pane_id is None:
            return
        try:
            self.tabs.get_tab(pane_id).label = self._tab_label(doc)
        except ValueError:
            pass

    def _sync_editor_to_doc(self, key: str) -> None:
        doc = self.store.get_key(key)
        editor_id = self._key_editor.get(key)
        editor = self._editors.get(editor_id) if editor_id else None
        if doc is not None and editor is not None:
            doc.update_text(editor.text)

    def _refresh_status(self) -> None:
        doc = self.current_doc()
        editor = self.current_editor()
        if doc is None or editor is None:
            self.status.set_status(filename="", language="", position="", modified=False)
            return
        line, col = editor.cursor_position
        self.status.set_status(
            filename=doc.name,
            language=doc.language or "text",
            position=f"{line}:{col}",
            modified=doc.dirty,
        )

    # -- opening / closing ----------------------------------------------------

    async def _open_path(self, path: str | Path) -> None:
        key = self.store.key_of(path)
        if self.store.is_open(path):
            self.tabs.active = self._pane_id[key]
            return
        try:
            doc = self.store.open(path)
        except ws.PathNotFound:
            self.notify(f"not found: {path}", severity="error")
            return
        except ws.FileReadError as exc:
            self.notify(f"cannot read {path}", severity="error")
            return

        self._id_counter += 1
        pane_id = f"pane-{self._id_counter}"
        editor_id = f"editor-{self._id_counter}"
        editor = EditorArea(doc, id=editor_id)
        pane = TabPane(self._tab_label(doc), editor, id=pane_id)

        self._pane_id[key] = pane_id
        self._doc_key[pane_id] = key
        self._key_editor[key] = editor_id
        self._editor_key[editor_id] = key
        self._editors[editor_id] = editor

        await self.tabs.add_pane(pane)
        self.tabs.active = pane_id
        editor.focus()
        self._refresh_status()

    def _close_key(self, key: str) -> None:
        pane_id = self._pane_id.pop(key, None)
        editor_id = self._key_editor.pop(key, None)
        if editor_id is not None:
            self._editor_key.pop(editor_id, None)
            self._editors.pop(editor_id, None)
        if pane_id is not None:
            self._doc_key.pop(pane_id, None)
            self.tabs.remove_pane(pane_id)
        self.store.close_key(key)
        self._refresh_status()

    def _close_callback(self, key: str, result: str | None) -> None:
        if result == "save":
            self._sync_editor_to_doc(key)
            try:
                self.store.save_key(key)
            except ws.FileWriteError as exc:
                self.notify(f"save failed: {exc}", severity="error")
                return
            self._close_key(key)
        elif result == "discard":
            self._close_key(key)
        # "cancel": do nothing

    # -- event handlers ------------------------------------------------------

    @on(DirectoryTree.FileSelected)
    async def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        await self._open_path(event.path)

    @on(DirectoryTree.DirectorySelected)
    def _on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if event.node.is_expanded:
            event.node.collapse()
        else:
            event.node.expand()

    @on(TabbedContent.TabActivated)
    def _on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        key = self._doc_key.get(event.pane.id)
        editor = self._editors.get(self._key_editor.get(key)) if key else None
        if editor is not None:
            editor.focus()
        self._refresh_status()

    def on_click(self, event: Click) -> None:
        if event.button != 2:
            return
        for pane_id, key in self._doc_key.items():
            if event.widget is self.tabs.get_tab(pane_id):
                event.stop()
                self._request_close_key(key)
                return

    @on(EditorArea.CloseRequested)
    def _on_editor_close_requested(self, event: EditorArea.CloseRequested) -> None:
        self.action_close_tab()

    @on(TextArea.Changed)
    def _on_text_changed(self, event: TextArea.Changed) -> None:
        key = self._editor_key.get(event.text_area.id)
        if key is None:
            return
        doc = self.store.get_key(key)
        if doc is None:
            return
        doc.update_text(event.text_area.text)
        self._update_tab_label(doc)
        self._refresh_status()

    @on(TextArea.SelectionChanged)
    def _on_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        if self._editor_key.get(event.text_area.id) == self.current_key():
            self._refresh_status()

    # -- actions -------------------------------------------------------------

    def action_save(self) -> None:
        key = self.current_key()
        if key is None:
            self.notify("no file open", severity="warning")
            return
        doc = self.store.get_key(key)
        self._sync_editor_to_doc(key)
        try:
            self.store.save_key(key)
        except ws.FileWriteError as exc:
            self.notify(f"save failed: {exc}", severity="error")
            return
        self._update_tab_label(doc)
        self._refresh_status()
        self.notify(f"saved {doc.name}", severity="information")

    def action_close_tab(self) -> None:
        key = self.current_key()
        if key is not None:
            self._request_close_key(key)

    def _request_close_key(self, key: str) -> None:
        self._sync_editor_to_doc(key)
        doc = self.store.get_key(key)
        if doc is None:
            return
        if doc.dirty:
            self.push_screen(
                ConfirmScreen(
                    f"{doc.name} has unsaved changes.",
                    [("save", "Save"), ("discard", "Discard"), ("cancel", "Cancel")],
                ),
                callback=lambda result: self._close_callback(key, result),
            )
        else:
            self._close_key(key)

    def _cycle_tab(self, delta: int) -> None:
        docs = self.store.documents()
        if not docs:
            return
        key = self.current_key()
        if key is None:
            target = docs[0]
        else:
            keys = [self.store.key_of(d.path) for d in docs]
            index = keys.index(key) if key in keys else -1
            target = docs[(index + delta) % len(docs)]
        self.tabs.active = self._pane_id[self.store.key_of(target.path)]

    def action_next_tab(self) -> None:
        self._cycle_tab(1)

    def action_prev_tab(self) -> None:
        self._cycle_tab(-1)

    def action_quick_switch(self) -> None:
        self.push_screen(
            QuickSwitchScreen(self.workspace, show_hidden=self.settings.show_hidden),
            callback=self._quick_switch_callback,
        )

    async def _quick_switch_callback(self, path: str | None) -> None:
        if path:
            await self._open_path(self.workspace.root / path)

    async def action_quit(self) -> None:
        dirty = [doc for doc in self.store.documents() if doc.dirty]
        if not dirty:
            self.exit()
            return
        self.push_screen(
            ConfirmScreen(
                f"{len(dirty)} file(s) have unsaved changes.",
                [("save", "Save all"), ("discard", "Discard all"), ("cancel", "Cancel")],
            ),
            callback=self._quit_callback,
        )

    def _quit_callback(self, result: str | None) -> None:
        if result == "save":
            for key in list(self._key_editor):
                self._sync_editor_to_doc(key)
            try:
                self.store.save_all()
            except ws.FileWriteError as exc:
                self.notify(f"save failed: {exc}", severity="error")
                return
            self.exit()
        elif result == "discard":
            self.exit()
        # "cancel": do nothing
