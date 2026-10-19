"""Command-line entry point for kvide."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .app import KvideApp
from .config import Settings
from .workspace import Workspace, WorkspaceError


def default_generators_path() -> Path | None:
    """Find an existing user configuration, never relative to the workspace."""
    if sys.platform == "win32":
        value = os.environ.get("APPDATA")
        if not value or not Path(value).is_absolute():
            return None
        directory = Path(value)
    else:
        value = os.environ.get("XDG_CONFIG_HOME")
        directory = (
            Path(value) if value and Path(value).is_absolute()
            else Path.home() / ".config"
        )
    path = directory / "kvide" / "generators.toml"
    return path if path.exists() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kvide",
        description="A small terminal code editor.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="project directory to open (default: current directory)",
    )
    parser.add_argument(
        "--icons",
        choices=["nerd", "text"],
        default="nerd",
        help="icon set to use (default: %(default)s)",
    )
    parser.add_argument(
        "--show-hidden",
        action="store_true",
        help="show hidden files and directories",
    )
    parser.add_argument(
        '--generators', type=Path,
        help='explicit trusted generator configuration (TOML)',
    )
    parser.add_argument(
        '--completion-extension', type=Path, action='append', default=[],
        help='run a trusted VS Code completion extension directory (repeatable; executes JavaScript)',
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"kvide {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings(
            root=args.path,
            show_hidden=args.show_hidden,
            icon_mode=args.icons,
            completion_extensions=args.completion_extension,
            generators_config=(
                args.generators if args.generators is not None
                else default_generators_path()
            ),
        )
        settings.validate()
        workspace = Workspace(settings.root)
    except (WorkspaceError, ValueError) as exc:
        print(f"kvide: {exc}", file=sys.stderr)
        return 1

    app = KvideApp(workspace, settings)
    app.run()
    return 0
