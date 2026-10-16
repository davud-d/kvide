"""Top header bar showing the application and project name."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


class ProjectHeader(Static):
    """A single-line header with the project name."""

    def __init__(self, project_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.project_name = project_name

    def render(self) -> Text:
        return Text(f" kvide · {self.project_name}", style="bold")
