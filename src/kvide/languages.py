"""Language detection by file extension.

The returned names are the Tree-sitter language names understood by Textual's
``TextArea`` widget. Only languages with a matching ``tree-sitter-<name>``
package are listed, so a detected name always has a parser available when the
``syntax`` extra is installed.
"""

from __future__ import annotations

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".rs": "rust",
    ".go": "go",
    ".sql": "sql",
    ".java": "java",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "bash",
    ".xml": "xml",
}


def detect_language(filename: str) -> str | None:
    """Return the editor language for *filename*, or ``None`` for plain text."""
    if "." not in filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    return LANGUAGE_BY_EXTENSION.get(ext)
