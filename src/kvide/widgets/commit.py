"""Commit tool window: selection, message and optional generator buttons."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Label, SelectionList, Static, TextArea

from ..generators import Generator, GeneratorError, generate
from ..git import Change, GitError, GitRepository
from ..icons import file_icon
from ..workspace import WorkspaceError


class CommitPanel(Vertical):
    """A persistent tool window; hiding it never loses the message draft."""

    BINDINGS = [
        Binding(f'ctrl+f{i + 1}', f'generate({i})', f'Generator {i + 1}', show=False, priority=True)
        for i in range(9)
    ] + [Binding('escape', 'files', 'Files', show=False)]

    def __init__(self, repository: GitRepository, generators: list[Generator], icon_mode: str) -> None:
        super().__init__(id='commit-panel')
        self.repository = repository
        self.generators = generators
        self.icon_mode = icon_mode
        self.busy = False
        self.ready = False
        self.revision = 0

    def compose(self) -> ComposeResult:
        yield Label('Commit', id='commit-title')
        yield Static('Select saved files. Space toggles a file.', id='commit-hint')
        yield SelectionList[Change](id='commit-files')
        yield Static('Open Commit to load changes.', id='commit-state', markup=False)
        with VerticalScroll(id='generator-tools'):
            for index, generator in enumerate(self.generators):
                shortcut = f'  Ctrl+F{index + 1}' if index < 9 else ''
                icon = generator.icon if self.icon_mode == 'nerd' else '*'
                label = Text.assemble((icon, generator.color or ''), f' {generator.name}{shortcut}')
                yield Button(label, id=f'generate-{index}', classes='generator-button')
        yield Label('Commit message', id='message-label')
        yield TextArea(id='commit-message', soft_wrap=True)
        with Horizontal(id='commit-actions'):
            yield Button('Commit', id='commit-submit', variant='primary', disabled=True)
            yield Button('Refresh', id='commit-refresh')

    def action_files(self) -> None:
        self.app.action_show_files()

    def _state(self, text: str) -> None:
        self.query_one('#commit-state', Static).update(text)

    def _busy(self, value: bool, text: str = '') -> None:
        self.busy = value
        for button in self.query(Button):
            button.disabled = value
        self.query_one('#commit-files', SelectionList).disabled = value
        self.query_one('#commit-message', TextArea).read_only = value
        if text:
            self._state(text)
        self._update_submit()

    def _update_submit(self) -> None:
        enabled = self.ready and bool(self.query_one('#commit-files', SelectionList).selected) and bool(self.query_one('#commit-message', TextArea).text.strip())
        self.query_one('#commit-submit', Button).disabled = self.busy or not enabled

    @on(SelectionList.SelectedChanged)
    @on(TextArea.Changed, '#commit-message')
    def _changed(self) -> None:
        self._update_submit()

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        event.stop()
        identity = event.button.id or ''
        if identity == 'commit-refresh':
            self.refresh_changes()
        elif identity == 'commit-submit':
            self.submit()
        elif identity.startswith('generate-'):
            self.action_generate(int(identity.split('-')[1]))

    @work
    async def refresh_changes(self) -> None:
        if self.busy:
            return
        self._busy(True, 'Loading changes...')
        files = self.query_one('#commit-files', SelectionList)
        previous = {c.path for c in files.selected}
        try:
            changes = await asyncio.to_thread(self.repository.changes)
            files.clear_options()
            files.add_options([
                (Text(f'{c.status} {file_icon(c.path, self.icon_mode)} {c.path}'), c, c.path in previous)
                for c in changes
            ])
            if changes:
                files.highlighted = 0
            self.ready = True
            self._state(f'{len(changes)} changed file(s)' if changes else 'No changes. Save a file, then Refresh.')
        except GitError as exc:
            self.ready = False
            files.clear_options()
            self._state(str(exc))
        finally:
            self._busy(False)
            self.revision += 1
            if self.display:
                self.query_one('#commit-files').focus()

    def action_generate(self, index: int) -> None:
        if self.busy or not self.ready or not self.display or self.app.screen.is_modal:
            return
        if 0 <= index < len(self.generators):
            self._generate(index)

    @work
    async def _generate(self, index: int) -> None:
        selected = list(self.query_one('#commit-files', SelectionList).selected)
        if not selected:
            self.app.notify('Select files before generating a message.', severity='warning')
            return
        generator = self.generators[index]
        message = self.query_one('#commit-message', TextArea)
        before = message.text
        self._busy(True, f'Generating with {generator.name}...')
        try:
            context = await asyncio.to_thread(self.repository.generation_context, selected)
            result = await asyncio.to_thread(generate, generator, context, self.repository.workspace.root)
            if message.text == before:
                message.load_text(result)
                self._state('Message generated. Review it, then press Commit.')
            else:
                self._state('Draft changed; generated message was not applied.')
        except (GitError, GeneratorError, WorkspaceError) as exc:
            self.app.notify(str(exc), severity='error', markup=False)
            self._state('Generation failed. Your draft is unchanged.')
        finally:
            self._busy(False)
            self.revision += 1

    @work
    async def submit(self) -> None:
        if self.busy or not self.ready:
            return
        selected = list(self.query_one('#commit-files', SelectionList).selected)
        message = self.query_one('#commit-message', TextArea)
        # Never silently commit an older on-disk version of an unsaved editor.
        paths = {self.repository.workspace.root / p for c in selected for p in c.paths}
        if any(doc.dirty and doc.path in paths for doc in self.app.store.documents()):
            self.app.notify('Save selected files before committing.', severity='warning')
            return
        self._busy(True, 'Committing selected files...')
        success = False
        try:
            result = await asyncio.to_thread(self.repository.commit, selected, message.text)
            message.load_text('')
            self.app.notify(result.strip(), markup=False)
            success = True
        except GitError as exc:
            self.app.notify(str(exc), severity='error', markup=False)
            self._state('Commit failed. Draft kept; selected files may be staged.')
        finally:
            self._busy(False)
        if success:
            self.refresh_changes()
