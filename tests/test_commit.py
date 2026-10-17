"""Selected-file Git operations and commit tool window integration."""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import sys
import time

import pytest
from textual.widgets import Button, SelectionList, TextArea

from kvide.app import KvideApp
from kvide.config import Settings
from kvide.generators import Generator, GeneratorError, generate, load_generators
from kvide.git import GitError, GitRepository
from kvide.screens import ConfirmScreen
from kvide.widgets.commit import CommitPanel
from kvide.workspace import Workspace


def git(root: Path, *args: str) -> str:
    result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True, check=True)
    return result.stdout


async def _wait_until(pilot, predicate, *, timeout: float = 15.0, what: str = "condition") -> None:
    """Poll until *predicate* is true, letting the app's workers progress."""
    end = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > end:
            raise AssertionError(f"timed out waiting for {what}")
        await pilot.pause()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Test')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    for name in ['a.txt', 'b.txt']:
        (tmp_path / name).write_text('original\n')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'Initial')
    return tmp_path


def test_selected_commit_excludes_other_staged_files(repo: Path) -> None:
    (repo / 'a.txt').write_text('changed a\n')
    (repo / 'b.txt').write_text('changed b\n')
    git(repo, 'add', 'b.txt')
    repository = GitRepository(Workspace(repo))
    selected = [c for c in repository.changes() if c.path == 'a.txt']
    repository.commit(selected, 'Only a')
    assert git(repo, 'show', '--format=', '--name-only', 'HEAD').strip() == 'a.txt'
    assert git(repo, 'diff', '--cached', '--name-only').strip() == 'b.txt'
    assert git(repo, 'show', 'HEAD:b.txt') == 'original\n'


def test_initial_commit_untracked_and_deletion(tmp_path: Path) -> None:
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Test')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    path = tmp_path / '-[new] file.txt'
    path.write_text('new file\n')
    repository = GitRepository(Workspace(tmp_path))
    selected = repository.changes()
    assert repository.generation_context(selected)['files'] == [path.name]
    repository.commit(selected, 'Initial selected file')
    assert git(tmp_path, 'show', f'HEAD:{path.name}') == 'new file\n'
    path.unlink()
    repository.commit(repository.changes(), 'Delete selected file')
    assert repository.changes() == []


def test_rename_and_unselected_index_preserved(repo: Path) -> None:
    git(repo, 'mv', 'a.txt', 'renamed.txt')
    (repo / 'b.txt').write_text('unrelated\n')
    git(repo, 'add', 'b.txt')
    repository = GitRepository(Workspace(repo))
    selected = [c for c in repository.changes() if c.original]
    assert selected[0].original == 'a.txt'
    repository.commit(selected, 'Rename a')
    assert git(repo, 'diff', '--cached', '--name-only').strip() == 'b.txt'
    assert git(repo, 'show', 'HEAD:renamed.txt') == 'original\n'


def test_git_validation_and_non_repository(repo: Path, tmp_path: Path) -> None:
    repository = GitRepository(Workspace(repo))
    with pytest.raises(GitError, match='Select'):
        repository.commit([], 'message')
    with pytest.raises(GitError, match='message'):
        repository.commit([], ' ')
    nested = repo / 'sub'
    nested.mkdir()
    with pytest.raises(GitError, match='root'):
        GitRepository(Workspace(nested)).changes()
    (repo / 'new.txt').write_text('new\n')
    selected = repository.changes()
    (repo / 'new.txt').unlink()
    with pytest.raises(GitError, match='Refresh'):
        repository.commit(selected, 'Stale')


def test_generator_protocol_and_config(tmp_path: Path) -> None:
    script = tmp_path / 'plugin.py'
    script.write_text('import json, sys\ncontext = json.load(sys.stdin)\nprint("Update " + context["files"][0])\n')
    icon = tmp_path / 'icon.txt'
    icon.write_text('\uf489\n')
    config = tmp_path / 'generators.toml'
    config.write_text(f'[[generators]]\nname = "Local"\ncommand = [{sys.executable!r}, {str(script)!r}]\nicon = "icon.txt"\n')
    generators = load_generators(Workspace(tmp_path), config)
    assert generators[0].icon == '\uf489'
    assert generate(generators[0], {'files': ['a.py']}, tmp_path) == 'Update a.py'
    script.write_text('print(\'{"error":{"code":"insufficient_funds","message":"Top up account"}}\')\n')
    with pytest.raises(GeneratorError, match='insufficient_funds: Top up'):
        generate(generators[0], {}, tmp_path)
    script.write_text('import sys\nprint("misleading success")\nsys.exit(2)\n')
    with pytest.raises(GeneratorError, match='code 2'):
        generate(generators[0], {}, tmp_path)
    script.write_text('import time\ntime.sleep(3)\n')
    with pytest.raises(GeneratorError):
        generate(Generator('Slow', (sys.executable, str(script)), timeout=1), {}, tmp_path)
    config.write_text('[[generators]]\nname = "Broken"\ncommand = "shell string"\n')
    with pytest.raises(GeneratorError, match='array'):
        load_generators(Workspace(tmp_path), config)


def test_commit_panel_flow(repo: Path) -> None:
    (repo / 'a.txt').write_text('changed\n')

    async def scenario() -> None:
        app = KvideApp(Workspace(repo), Settings(root=repo, icon_mode='text'))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            panel = app.query_one(CommitPanel)
            files = panel.query_one(SelectionList)
            message = panel.query_one('#commit-message', TextArea)
            assert not panel.display

            await pilot.press('ctrl+g')
            assert panel.display
            await _wait_until(pilot, lambda: panel.revision > 0, what='changes loaded')
            assert files.option_count == 1
            assert panel.query_one('#commit-submit', Button).disabled

            await pilot.press('space')
            message.load_text('Commit from panel')
            await pilot.pause()
            assert not panel.query_one('#commit-submit', Button).disabled

            # No controls overlap or fall outside the minimum-size window.
            for selector in ['#commit-files', '#commit-message', '#commit-submit', '#commit-refresh']:
                region = panel.query_one(selector).region
                assert region.width > 0 and region.height > 0
                assert 0 <= region.y < region.bottom <= 23

            await pilot.press('ctrl+b')
            assert not panel.display
            assert message.text == 'Commit from panel'

            rev = panel.revision
            await pilot.press('ctrl+g')
            assert message.text == 'Commit from panel'
            await _wait_until(pilot, lambda: panel.revision > rev, what='changes reloaded')

            assert await pilot.click('#commit-submit')
            await _wait_until(pilot, lambda: files.option_count == 0, what='commit finished')
            assert git(repo, 'log', '-1', '--format=%s').strip() == 'Commit from panel'
            assert message.text == ''
            assert files.option_count == 0

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_generation_focus_modal_scope_and_failure(repo: Path) -> None:
    (repo / 'a.txt').write_text('changed\n')
    script = repo / 'generator.py'
    script.write_text('print("Generated title")\n')

    async def scenario() -> None:
        app = KvideApp(Workspace(repo), Settings(root=repo))
        app.generators = [Generator('Test', (sys.executable, str(script)))]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = app.query_one(CommitPanel)
            message = panel.query_one('#commit-message', TextArea)
            files = panel.query_one(SelectionList)

            await app._open_path(repo / 'a.txt')
            await pilot.press('ctrl+f1')
            await pilot.pause()
            assert message.text == ''

            await pilot.press('ctrl+g')
            await _wait_until(pilot, lambda: panel.revision > 0, what='changes loaded')
            files.select(next(c for c in app.query_one(CommitPanel).repository.changes() if c.path == 'a.txt'))
            message.load_text('My draft')
            message.focus()

            app.push_screen(ConfirmScreen('Modal', [('cancel', 'Cancel')]))
            await pilot.pause()
            await pilot.press('ctrl+f1')
            await pilot.pause()
            assert message.text == 'My draft'

            await pilot.press('escape')
            await pilot.pause()
            message.focus()

            rev = panel.revision
            await pilot.press('ctrl+f1')
            await _wait_until(pilot, lambda: panel.revision > rev, what='generation')
            assert message.text == 'Generated title'
            assert git(repo, 'log', '-1', '--format=%s').strip() == 'Initial'

            script.write_text('print(\'{"error":{"code":"overloaded","message":"Try later"}}\')\n')
            rev = panel.revision
            await pilot.click('#generate-0')
            await _wait_until(pilot, lambda: panel.revision > rev, what='generator error handled')
            assert message.text == 'Generated title'
            assert not panel.busy

            # Render the wide layout too, and inspect key text in the compositor.
            screen_text = '\n'.join(strip.text for strip in app.screen._compositor.render_strips())
            assert 'Commit message' in screen_text
            assert 'Refresh' in screen_text
            assert 'Generated title' in screen_text

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))
