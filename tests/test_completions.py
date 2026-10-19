"""Completion range, host lifecycle and headless editor integration."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from textual.widgets import OptionList, Static

from kvide.app import KvideApp
from kvide.completions import CompletionError, CompletionService, completion_range, python_column, utf16_column
from kvide.config import Settings
from kvide.workspace import Workspace
from kvide.widgets.completion import CompletionMenu


def test_utf16_and_ranges() -> None:
    assert utf16_column("a😀b", 2) == 3
    assert python_column("a😀b", 3) == 2
    with pytest.raises(CompletionError):
        python_column("a😀b", 2)
    assert completion_range("foo.bar", {}, (0, 7)) == ((0, 4), (0, 7))
    with pytest.raises(CompletionError):
        completion_range("abc", {"range": {"start": {"line": 0, "character": 2}, "end": {"line": 0, "character": 8}}}, (0, 3))


@pytest.fixture
def extension(tmp_path: Path) -> Path:
    if not shutil.which("node"):
        pytest.skip("Node.js is required")
    ext = tmp_path / "extension"
    ext.mkdir()
    (ext / "package.json").write_text(json.dumps({"name": "test-completion", "main": "./index.js"}))
    (ext / "index.js").write_text('''
const vscode = require('vscode');
exports.activate = context => {
 context.subscriptions.push(vscode.languages.registerCompletionItemProvider('python', {
  async provideCompletionItems(document, position) {
   const item = new vscode.CompletionItem('print', vscode.CompletionItemKind.Function);
   item.insertText = 'print()';
   item.detail = 'Print a value';
   item.documentation = new vscode.MarkdownString('Output documentation');
   item.range = document.getWordRangeAtPosition(position);
   return [item];
  }
 }));
};
''')
    return ext


def test_service_process_cleanup(extension: Path, tmp_path: Path) -> None:
    async def scenario():
        service = CompletionService([extension], tmp_path)
        result = await service.complete(tmp_path / "a.py", "python", "pri", (0, 3))
        assert result[0]["insertText"] == "print()"
        process = service.hosts[0].process
        await service.close()
        assert process.returncode is not None
    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (160, 50)])
def test_completion_keyboard_integration(extension: Path, tmp_path: Path, size: tuple[int, int]) -> None:
    path = tmp_path / "a.py"
    path.write_text("pri")
    async def scenario():
        app = KvideApp(Workspace(tmp_path), Settings(root=tmp_path, completion_extensions=[extension]))
        async with app.run_test(size=size) as pilot:
            await app._open_path(path)
            editor = app.current_editor()
            editor.move_cursor((0, 3))
            await pilot.pause()
            await pilot.press("ctrl+space")
            await pilot.pause(0.5)
            menu = app.query_one(CompletionMenu)
            assert menu.query_one(OptionList).option_count == 1
            assert "Output documentation" in str(menu.query_one(Static).render())
            assert menu.region.x >= 0 and menu.region.right <= size[0]
            assert menu.region.y >= 0 and menu.region.bottom <= size[1]
            assert editor.has_focus
            await pilot.press("escape")
            await pilot.pause()
            assert editor.text == "pri"
            assert editor.completion_menu is None
            await pilot.press("ctrl+space")
            await pilot.pause(0.3)
            await pilot.press("tab")
            await pilot.pause()
            assert editor.text == "print()"
            assert app.current_doc().dirty
            await pilot.press("ctrl+z")
            await pilot.pause()
            assert editor.text == "pri"
    asyncio.run(scenario())


def test_auto_completion(extension: Path, tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("")
    async def scenario():
        app = KvideApp(Workspace(tmp_path), Settings(root=tmp_path, completion_extensions=[extension]))
        async with app.run_test() as pilot:
            await app._open_path(path)
            await pilot.press("p", "r", "i")
            await pilot.pause(0.6)
            assert app.current_editor().completion_menu is not None
            await pilot.press("enter")
            await pilot.pause()
            assert app.current_editor().text == "print()"
    asyncio.run(scenario())


def test_late_response_is_not_displayed(extension: Path, tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("pri")
    async def scenario():
        app = KvideApp(Workspace(tmp_path), Settings(root=tmp_path, completion_extensions=[extension]))
        started, release = asyncio.Event(), asyncio.Event()
        async def delayed(*args, **kwargs):
            started.set()
            await release.wait()
            return [{"label": "print", "insertText": "print()"}]
        app.completions.complete = delayed
        async with app.run_test() as pilot:
            await app._open_path(path)
            editor = app.current_editor()
            editor.move_cursor((0, 3))
            app.action_complete()
            await started.wait()
            editor.move_cursor((0, 0))
            release.set()
            await pilot.pause()
            assert editor.completion_menu is None
            assert editor.text == "pri"
    asyncio.run(scenario())


def test_provider_error_preserves_buffer(extension: Path, tmp_path: Path) -> None:
    (extension / "index.js").write_text("exports.activate = () => { throw new Error('provider broke'); };")
    path = tmp_path / "a.py"
    path.write_text("pri")
    async def scenario():
        app = KvideApp(Workspace(tmp_path), Settings(root=tmp_path, completion_extensions=[extension]))
        async with app.run_test() as pilot:
            await app._open_path(path)
            app.current_editor().move_cursor((0, 3))
            app.action_complete()
            await pilot.pause(0.4)
            assert app.current_editor().text == "pri"
            assert app.current_editor().completion_menu is None
            assert any("provider broke" in str(n.message) for n in app._notifications)
    asyncio.run(scenario())


def test_example_extension(tmp_path: Path) -> None:
    if not shutil.which("node"):
        pytest.skip("Node.js is required")
    async def scenario():
        service = CompletionService([Path("examples/completion-extension")], tmp_path)
        try:
            items = await service.complete(tmp_path / "a.py", "python", "pri", (0, 3))
            assert items[0]["label"] == "print"
            assert items[0]["insertText"] == "print()"
        finally:
            await service.close()
    asyncio.run(scenario())


def test_mouse_accepts_completion(extension: Path, tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("pri")
    async def scenario():
        app = KvideApp(Workspace(tmp_path), Settings(root=tmp_path, completion_extensions=[extension]))
        async with app.run_test() as pilot:
            await app._open_path(path)
            app.current_editor().move_cursor((0, 3))
            app.action_complete()
            await pilot.pause(0.4)
            options = app.query_one(CompletionMenu).query_one(OptionList)
            await pilot.click(options, offset=(1, 0))
            await pilot.pause()
            assert app.current_editor().text == "print()"
    asyncio.run(scenario())


@pytest.mark.parametrize("response", ["null", "[]", '"unexpected"', "42"])
def test_invalid_protocol_response_closes_host(extension: Path, tmp_path: Path, response: str) -> None:
    (extension / "index.js").write_text(
        f"process.stdout.write({json.dumps(response + chr(10))});\nexports.activate = () => {{}};\n"
    )

    async def scenario():
        service = CompletionService([extension], tmp_path)
        try:
            with pytest.raises(CompletionError, match="invalid response object"):
                await service.complete(tmp_path / "a.py", "python", "pri", (0, 3))
            assert service.hosts[0].process is None
        finally:
            await service.close()

    asyncio.run(scenario())


@pytest.fixture
def inline_extension(tmp_path: Path) -> Path:
    if not shutil.which("node"):
        pytest.skip("Node.js is required")
    ext = tmp_path / "inline-extension"
    ext.mkdir()
    (ext / "package.json").write_text(json.dumps({"name": "test-inline", "main": "./index.js"}))
    (ext / "index.js").write_text('''
const vscode = require('vscode');
exports.activate = context => {
 context.subscriptions.push(vscode.languages.registerInlineCompletionItemProvider('*', {
  provideInlineCompletionItems(document, position) {
   return [new vscode.InlineCompletionItem('nt(value)\\nmore', new vscode.Range(position, position))];
  }
 }));
};
''')
    return ext


def test_inline_service_returns_the_text_after_the_cursor(inline_extension: Path, tmp_path: Path) -> None:
    async def scenario():
        service = CompletionService([inline_extension], tmp_path)
        assert await service.inline(tmp_path / "a.py", "python", "pri", (0, 3), automatic=True) == "nt(value)\nmore"
        await service.close()
    asyncio.run(scenario())


def test_ghost_text_is_accepted_with_tab_and_dismissed_with_escape(inline_extension: Path, tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("")
    async def scenario():
        app = KvideApp(Workspace(tmp_path), Settings(root=tmp_path, completion_extensions=[inline_extension]))
        async with app.run_test() as pilot:
            await app._open_path(path)
            editor = app.current_editor()
            await pilot.press("p", "r", "i")
            await pilot.pause(0.8)
            assert editor.suggestion == "nt(value)"
            await pilot.press("n")
            assert editor.suggestion == "t(value)"
            await pilot.press("backspace")
            assert editor.suggestion == ""
            await pilot.press("n")
            await pilot.pause(0.8)
            await pilot.press("escape")
            assert editor.suggestion == "" and editor.text == "prin"
            await pilot.press("t")
            await pilot.pause(0.8)
            await pilot.press("tab")
            assert editor.text == "printnt(value)"
    asyncio.run(scenario())
