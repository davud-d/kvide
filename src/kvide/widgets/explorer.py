"""Project file explorer: a lazily loaded directory tree."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.widgets import DirectoryTree

from .. import icons
from ..workspace import is_hidden_name, is_ignored_dir


class ProjectExplorer(DirectoryTree):
    """A directory tree that loads each folder on demand.

    Directories in :data:`kvide.workspace.IGNORED_DIRS` are never shown, and
    hidden files are skipped unless ``show_hidden`` is set. Icons come from
    :mod:`kvide.icons` and fall back to text when the terminal lacks a Nerd
    Font.
    """

    BINDINGS = [
        Binding("left", "collapse_or_parent", "Collapse or parent", show=False),
        Binding("right", "expand_or_child", "Expand or child", show=False),
    ]

    def action_collapse_or_parent(self) -> None:
        """Collapse the current folder, otherwise move to its parent."""
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif node.parent is not None:
            self.move_cursor(node.parent)

    def action_expand_or_child(self) -> None:
        """Expand the current folder, otherwise move to its first child."""
        node = self.cursor_node
        if node is None or not node.allow_expand:
            return
        if not node.is_expanded:
            node.expand()
        elif node.children:
            self.move_cursor(node.children[0])

    def __init__(
        self,
        path: str | Path,
        *,
        icon_mode: str = "nerd",
        show_hidden: bool = False,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        self.icon_mode = icon_mode
        self.show_hidden = show_hidden
        super().__init__(path, name=name, id=id)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        for path in paths:
            if is_ignored_dir(path.name):
                continue
            if not self.show_hidden and is_hidden_name(path.name):
                continue
            yield path

    def render_label(
        self, node, base_style: Style, style: Style
    ) -> Text:
        label = node._label.copy()
        label.stylize(style)

        if not self.is_mounted:
            return label

        if node.allow_expand:
            icon = (
                icons.folder_open(self.icon_mode)
                if node.is_expanded
                else icons.folder(self.icon_mode)
            )
            label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            name = node.data.path.name if node.data is not None else ""
            icon = icons.file_icon(name, self.icon_mode)
            label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True)
            )
            label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style(
                    "directory-tree--extension", partial=True
                ),
            )

        if label.plain.startswith("."):
            label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden", partial=True)
            )

        if icon:
            return Text.assemble(icon + " ", label)
        return label
