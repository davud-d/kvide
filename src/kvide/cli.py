"""Command-line entry point for kvide."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .app import KvideApp
from .config import Settings
from .workspace import Workspace, WorkspaceError


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
        )
        settings.validate()
        workspace = Workspace(settings.root)
    except (WorkspaceError, ValueError) as exc:
        print(f"kvide: {exc}", file=sys.stderr)
        return 1

    app = KvideApp(workspace, settings)
    app.run()
    return 0
