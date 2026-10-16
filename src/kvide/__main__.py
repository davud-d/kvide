"""Allow ``python -m kvide`` to launch the editor."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
