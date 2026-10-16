"""End-to-end tests driving the app with Textual's headless pilot."""

from __future__ import annotations

import asyncio
from pathlib import Path

from kvide.app import KvideApp
from kvide.config import Settings
from kvide.screens import ConfirmScreen
from kvide.widgets import ProjectExplorer, ProjectHeader, StatusBar
from kvide.workspace import Workspace


def _make_app(root: Path) -> KvideApp:
    return KvideApp(Workspace(root), Settings(root=root))


def _run(coro) -> None:
    asyncio.run(coro)


def test_app_mounts_core_widgets(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one(ProjectExplorer) is not None
            assert app.query_one(StatusBar) is not None
            assert app.query_one(ProjectHeader) is not None

    _run(scenario())


def test_open_file_creates_tab_with_content(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            doc = app.current_doc()
            assert doc is not None and doc.name == "a.py"
            editor = app.current_editor()
            assert editor is not None
            assert editor.text == "x = 1\n"
            assert app.tabs.tab_count == 1

    _run(scenario())


def test_edit_marks_dirty_and_updates_tab(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("y = 2\n")
            await pilot.pause()
            doc = app.current_doc()
            assert doc.dirty is True
            tab = app.tabs.get_tab(app._pane_id[app.current_key()])
            assert "●" in tab.label_text

    _run(scenario())


def test_save_writes_to_disk_and_clears_dirty(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("y = 2\n")
            await pilot.pause()
            app.action_save()
            await pilot.pause()
            assert app.current_doc().dirty is False
            assert (project / "src" / "a.py").read_text(encoding="utf-8") == (
                "y = 2\nx = 1\n"
            )

    _run(scenario())


def test_ctrl_s_binding_saves(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("y = 2\n")
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert app.current_doc().dirty is False

    _run(scenario())


def test_switch_between_open_documents(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await app._open_path(project / "src" / "b.py")
            await pilot.pause()
            assert app.current_doc().name == "b.py"
            app.action_prev_tab()
            await pilot.pause()
            assert app.current_doc().name == "a.py"
            app.action_next_tab()
            await pilot.pause()
            assert app.current_doc().name == "b.py"

    _run(scenario())


def test_explorer_lists_and_filters_files(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            explorer = app.query_one(ProjectExplorer)
            names = {child.label.plain for child in explorer.root.children}
            assert "src" in names
            assert "notes.md" in names
            assert ".hidden" not in names
            assert "node_modules" not in names

    _run(scenario())


def test_close_clean_tab(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await app._open_path(project / "src" / "b.py")
            await pilot.pause()
            assert app.tabs.tab_count == 2
            app.action_close_tab()
            await pilot.pause()
            assert app.tabs.tab_count == 1
            assert app.current_doc().name == "a.py"

    _run(scenario())


def test_ctrl_w_closes_tab_from_editor(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            assert app.current_editor() is not None
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.tabs.tab_count == 0
            assert app.current_doc() is None

    _run(scenario())


def test_close_dirty_tab_discard(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("changed\n")
            await pilot.pause()
            app.action_close_tab()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            await pilot.click("#choice-1")  # Discard
            await pilot.pause()
            assert app.tabs.tab_count == 0
            assert app.current_doc() is None

    _run(scenario())


def test_close_dirty_tab_save(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("changed\n")
            await pilot.pause()
            app.action_close_tab()
            await pilot.pause()
            await pilot.click("#choice-0")  # Save
            await pilot.pause()
            assert app.tabs.tab_count == 0
            assert (project / "src" / "a.py").read_text(encoding="utf-8").startswith(
                "changed"
            )

    _run(scenario())


def test_close_dirty_tab_cancel_keeps_document(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("changed\n")
            await pilot.pause()
            app.action_close_tab()
            await pilot.pause()
            await pilot.click("#choice-2")  # Cancel
            await pilot.pause()
            assert app.tabs.tab_count == 1
            assert app.current_doc().dirty is True

    _run(scenario())


def test_quit_with_dirty_documents_prompts(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app._open_path(project / "src" / "a.py")
            await pilot.pause()
            app.current_editor().insert("changed\n")
            await pilot.pause()
            await app.action_quit()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            await pilot.click("#choice-2")  # Cancel
            await pilot.pause()
            assert app.current_doc() is not None
            assert app.current_doc().dirty is True

    _run(scenario())


def test_middle_click_closes_clicked_tab(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await app._open_path(project / "src" / "a.py")
            first_key = app.current_key()
            first_pane = app._pane_id[first_key]
            await app._open_path(project / "src" / "b.py")
            await pilot.pause()
            assert await pilot.click(app.tabs.get_tab(first_pane), button=2)
            await pilot.pause()
            assert app.store.get_key(first_key) is None
            assert app.tabs.tab_count == 1
            assert app.current_doc().name == "b.py"
            assert await pilot.click(app.tabs.get_tab(app.tabs.active), button=2)
            await pilot.pause()
            assert app.tabs.tab_count == 0
            assert app.current_doc() is None

    _run(scenario())


def test_middle_click_dirty_tab_choices(project: Path) -> None:
    async def scenario(choice: int) -> None:
        path = project / "src" / "a.py"
        path.write_text("x = 1\n", encoding="utf-8")
        app = _make_app(project)
        async with app.run_test() as pilot:
            await app._open_path(path)
            first_key = app.current_key()
            first_pane = app._pane_id[first_key]
            app.current_editor().insert("changed\n")
            await pilot.pause()
            await app._open_path(project / "src" / "b.py")
            await pilot.pause()
            assert await pilot.click(app.tabs.get_tab(first_pane), button=2)
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            assert app.tabs.tab_count == 2
            assert await pilot.click(f"#choice-{choice}")
            await pilot.pause()
            if choice == 2:
                assert app.tabs.tab_count == 2
                assert app.store.get_key(first_key).dirty
            else:
                assert app.tabs.tab_count == 1
                assert app.store.get_key(first_key) is None
                assert app.current_doc().name == "b.py"
            expected = "changed\nx = 1\n" if choice == 0 else "x = 1\n"
            assert path.read_text(encoding="utf-8") == expected

    for choice in range(3):
        _run(scenario(choice))


def test_left_click_switches_without_closing(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await app._open_path(project / "src" / "a.py")
            first_pane = app.tabs.active
            await app._open_path(project / "src" / "b.py")
            await pilot.pause()
            assert await pilot.click(app.tabs.get_tab(first_pane))
            await pilot.pause()
            assert app.tabs.tab_count == 2
            assert app.current_doc().name == "a.py"
            assert await pilot.click(app.current_editor(), button=2)
            await pilot.pause()
            assert app.tabs.tab_count == 2

    _run(scenario())


def test_explorer_arrow_navigation(project: Path) -> None:
    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            explorer = app.query_one(ProjectExplorer)
            explorer.focus()
            folder = next(
                node for node in explorer.root.children if node.label.plain == "src"
            )
            explorer.move_cursor(folder)
            assert not folder.is_expanded

            await pilot.press("right")
            await pilot.pause()
            assert folder.is_expanded
            assert explorer.cursor_node is folder
            assert folder.children

            await pilot.press("right")
            assert explorer.cursor_node is folder.children[0]
            await pilot.press("right")
            assert explorer.cursor_node is folder.children[0]
            assert app.tabs.tab_count == 0

            await pilot.press("left")
            assert explorer.cursor_node is folder
            assert folder.is_expanded
            await pilot.press("left")
            assert not folder.is_expanded
            assert explorer.cursor_node is folder
            await pilot.press("left")
            assert explorer.cursor_node is explorer.root
            await pilot.press("left")
            assert not explorer.root.is_expanded
            await pilot.press("left")
            assert explorer.cursor_node is explorer.root
            await pilot.press("right")
            assert explorer.root.is_expanded

    _run(scenario())


def test_explorer_arrows_on_empty_folder(project: Path) -> None:
    (project / "empty").mkdir()

    async def scenario() -> None:
        app = _make_app(project)
        async with app.run_test() as pilot:
            await pilot.pause()
            explorer = app.query_one(ProjectExplorer)
            explorer.focus()
            folder = next(
                node for node in explorer.root.children if node.label.plain == "empty"
            )
            explorer.move_cursor(folder)
            await pilot.press("right")
            await pilot.pause()
            assert folder.is_expanded
            assert not folder.children
            await pilot.press("right")
            assert explorer.cursor_node is folder
            await pilot.press("left")
            assert not folder.is_expanded
            assert explorer.cursor_node is folder
            await pilot.press("left")
            assert explorer.cursor_node is explorer.root

    _run(scenario())
