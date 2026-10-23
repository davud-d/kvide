"""Built-in terminal panel for running commands.

Pure Textual widget on top of ``asyncio`` subprocesses; it does not import
anything from the editing core.
"""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from rich.text import Text
from textual import on
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widgets import Input, RichLog

TIMEOUT = 30.0
"""Seconds a single command may run before it is killed."""

HISTORY_LIMIT = 100


class TerminalPane(Container):
    """A command panel: runs a line through the shell and shows its output.

    This is not a pseudo-terminal (no PTY), so interactive programs will not
    work; it is a runner for one-shot commands such as ``pytest`` or ``git
    status``, with scrollback and an up/down command history.
    """

    DEFAULT_CSS = """
    TerminalPane {
        display: none;
        height: 12;
        border-top: solid $primary;
        background: $surface-darken-2;
    }

    TerminalPane #terminal-output {
        height: 1fr;
        background: $surface-darken-2;
        border: none;
        color: $text;
        padding: 0 1;
    }

    TerminalPane #terminal-input {
        height: 1;
        border: none;
        background: $surface-darken-2;
        padding: 0 1;
    }

    TerminalPane #terminal-input:focus {
        background: $surface-darken-1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close terminal"),
    ]

    class Closed(Message):
        """Posted when the panel hides itself and focus should move away."""

    def __init__(self, cwd: Path | str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cwd = str(cwd) if cwd is not None else "."
        self._history: list[str] = []
        self._history_index = 0
        self._command_running = False

    def compose(self):
        with Vertical():
            yield RichLog(id="terminal-output", markup=False, wrap=True, max_lines=2000)
            yield Input(id="terminal-input", placeholder="command, Esc to close")

    def on_mount(self) -> None:
        self.query_one("#terminal-output", RichLog).write(
            Text(f"kvide terminal — {self.cwd}", style="dim")
        )

    # -- visibility ----------------------------------------------------------

    def show_terminal(self) -> None:
        """Make the panel visible and focus the command input."""
        self.display = True
        self.query_one("#terminal-input", Input).focus()

    def hide_terminal(self) -> None:
        """Hide the panel."""
        self.display = False

    def toggle_terminal(self) -> None:
        """Show the panel, or hide it if it is already visible."""
        if self.display:
            self.hide_terminal()
        else:
            self.show_terminal()

    def action_close(self) -> None:
        self.hide_terminal()
        self.post_message(self.Closed())

    def set_cwd(self, cwd: Path | str) -> None:
        """Set the working directory used for command execution."""
        self.cwd = str(cwd)

    def clear_output(self) -> None:
        """Clear the scrollback."""
        self.query_one("#terminal-output", RichLog).clear()

    # -- history -------------------------------------------------------------

    def _remember(self, command: str) -> None:
        if not self._history or self._history[-1] != command:
            self._history.append(command)
            del self._history[:-HISTORY_LIMIT]
        self._history_index = len(self._history)

    def _recall(self, delta: int) -> None:
        if not self._history:
            return
        index = max(0, min(len(self._history), self._history_index + delta))
        field = self.query_one("#terminal-input", Input)
        field.value = "" if index == len(self._history) else self._history[index]
        field.cursor_position = len(field.value)
        self._history_index = index

    def on_key(self, event) -> None:
        if not self.query_one("#terminal-input", Input).has_focus:
            return
        if event.key == "up":
            event.stop()
            event.prevent_default()
            self._recall(-1)
        elif event.key == "down":
            event.stop()
            event.prevent_default()
            self._recall(1)

    # -- running -------------------------------------------------------------

    @on(Input.Submitted, "#terminal-input")
    async def _on_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        command = event.value.strip()
        if not command:
            return
        field = self.query_one("#terminal-input", Input)
        if self._command_running:
            self._write(Text("a command is still running", style="yellow"))
            return
        field.value = ""
        self._remember(command)
        if command in {"clear", "cls"}:
            self.clear_output()
            return
        self._write(Text(f"$ {command}", style="bold cyan"))
        # Reserve the runner before the worker gets its first event-loop turn.
        self._command_running = True
        self.run_worker(self._run_command(command), group="terminal-command")

    def _write(self, line: Text | str) -> None:
        self.query_one("#terminal-output", RichLog).write(line)

    async def _run_command(self, command: str) -> None:
        """Run one shell command, streaming nothing but reporting everything."""
        self._command_running = True
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=self.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            self._command_running = False
            self._write(Text(f"cannot start: {exc}", style="red"))
            return

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=TIMEOUT
            )
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            self._write(Text(f"killed after {TIMEOUT:.0f}s", style="red"))
            return
        finally:
            self._command_running = False

        for chunk, style in ((stdout, None), (stderr, "red")):
            text = chunk.decode("utf-8", errors="replace").rstrip("\n")
            if not text:
                continue
            for line in text.split("\n"):
                self._write(Text(line, style=style) if style else line)

        if process.returncode:
            self._write(Text(f"exit code: {process.returncode}", style="yellow"))
