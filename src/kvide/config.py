"""Application configuration, kept independent of the UI layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .icons import VALID_MODES


@dataclass
class Settings:
    """User-facing settings gathered from the command line."""

    root: Path = field(default_factory=Path.cwd)
    show_hidden: bool = False
    icon_mode: str = "nerd"
    generators_config: Path | None = None
    completion_extensions: list[Path] = field(default_factory=list)

    def validate(self) -> None:
        """Normalize and check the settings before the app starts."""
        self.root = Path(self.root).expanduser().resolve()
        if self.icon_mode not in VALID_MODES:
            raise ValueError(
                f"unknown icon mode {self.icon_mode!r}; expected one of {VALID_MODES}"
            )
