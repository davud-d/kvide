"""Headless coverage for the opt-in shell command panel."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.widgets import Input

from kvide.app import KvideApp
from kvide.cli import build_parser, main
from kvide.config import Settings
from kvide.widgets import ProjectExplorer, TerminalPane
from kvide.workspace import Workspace


def test_terminal_cli_flag(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert not build_parser().parse_args([]).enable_terminal
    captured = []
    monkeypatch.setattr("kvide.cli.default_generators_path", lambda: None)
    monkeypatch.setattr(KvideApp, "run", lambda app: captured.append(app.settings))
    assert main([str(project), "--enable-terminal"]) == 0
    assert captured[0].enable_terminal


def test_terminal_disabled_by_default(project: Path) -> None:
    async def scenario() -> None:
        app = KvideApp(Workspace(project), Settings(root=project))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.query(TerminalPane)
            app.action_toggle_terminal()
            assert not app.query(TerminalPane)

    asyncio.run(scenario())


def test_terminal_toggle_focus_and_history(project: Path) -> None:
    async def scenario() -> None:
        app = KvideApp(Workspace(project), Settings(root=project, enable_terminal=True))
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(TerminalPane)
            assert not panel.display
            assert panel.cwd == str(project)
            await pilot.press("alt+minus")
            await pilot.pause()
            field = panel.query_one(Input)
            assert panel.display and field.has_focus
            assert panel.region.height > 0 and field.region.height > 0
            panel._remember("first")
            panel._remember("second")
            await pilot.press("up")
            assert field.value == "second"
            await pilot.press("up")
            assert field.value == "first"
            await pilot.press("down", "down")
            assert field.value == ""
            await pilot.press("escape")
            await pilot.pause()
            assert not panel.display
            assert app.query_one(ProjectExplorer).has_focus
            await app._open_path(project / "src" / "a.py")
            await pilot.press("alt+minus")
            await pilot.pause()
            assert panel.display and field.has_focus
            await pilot.press("alt+minus")
            await pilot.pause()
            assert not panel.display
            assert app.current_editor().has_focus

    asyncio.run(scenario())


def test_terminal_command_results_and_cleanup(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        app = KvideApp(Workspace(project), Settings(root=project, enable_terminal=True))
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(TerminalPane)
            output = []
            monkeypatch.setattr(panel, "_write", lambda text: output.append(str(text)))
            await panel._run_command("pwd")
            assert str(project) in output
            await panel._run_command("printf 'hello'; printf 'problem' >&2; exit 7")
            assert "hello" in output
            assert "problem" in output
            assert "exit code: 7" in output
            monkeypatch.setattr("kvide.widgets.terminal.TIMEOUT", 0.05)
            await asyncio.wait_for(panel._run_command("sleep 10"), timeout=2)
            assert any("killed after" in line for line in output)
            assert not panel._command_running
            monkeypatch.setattr("kvide.widgets.terminal.TIMEOUT", 30)
            task = asyncio.create_task(panel._run_command("sleep 10"))
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
            assert not panel._command_running
            panel.set_cwd(project / "missing")
            await panel._run_command("pwd")
            assert any("cannot start:" in line for line in output)
            assert not panel._command_running

    asyncio.run(scenario())


def test_submitted_command_keeps_ui_responsive(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        app = KvideApp(Workspace(project), Settings(root=project, enable_terminal=True))
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(TerminalPane)
            started = asyncio.Event()
            finish = asyncio.Event()
            completed = asyncio.Event()

            async def run(command: str) -> None:
                panel._command_running = True
                started.set()
                await finish.wait()
                panel._command_running = False
                completed.set()

            monkeypatch.setattr(panel, "_run_command", run)
            app.action_toggle_terminal()
            field = panel.query_one(Input)
            field.value = "example"
            await pilot.pause()
            assert field.has_focus
            await pilot.press("enter")
            await asyncio.wait_for(started.wait(), timeout=2)
            await pilot.press("escape")
            await pilot.pause()
            assert not panel.display
            assert panel._history == ["example"]
            finish.set()
            await asyncio.wait_for(completed.wait(), timeout=2)
            assert not panel._command_running

    asyncio.run(scenario())


def test_submissions_reserve_runner_before_worker_starts(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        app = KvideApp(Workspace(project), Settings(root=project, enable_terminal=True))
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(TerminalPane)
            field = panel.query_one(Input)
            scheduled = []

            def defer_worker(work, **kwargs):
                scheduled.append(work)
                work.close()

            monkeypatch.setattr(panel, "run_worker", defer_worker)
            await panel._on_submitted(Input.Submitted(field, "first"))
            await panel._on_submitted(Input.Submitted(field, "second"))
            assert len(scheduled) == 1
            assert panel._history == ["first"]

    asyncio.run(scenario())


def test_busy_submission_preserves_command(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        app = KvideApp(Workspace(project), Settings(root=project, enable_terminal=True))
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(TerminalPane)
            field = panel.query_one(Input)
            panel._command_running = True
            field.value = "next command"
            await panel._on_submitted(Input.Submitted(field, field.value))
            assert field.value == "next command"
            assert panel._history == []

    asyncio.run(scenario())
