"""PyInstaller entry script.

``src/kvide/__main__.py`` uses a relative import and cannot be frozen as a
top-level script, so the bundled binary starts here instead.
"""

from __future__ import annotations

import sys

from kvide.cli import main

if __name__ == "__main__":
    sys.exit(main())
