"""Terminal icons with a plain-text fallback mode.

Glyphs in the ``nerd`` mode come from the Nerd Fonts project
(https://www.nerdfonts.com/) and require a Nerd Font for correct rendering.
The ``text`` mode uses ASCII markers that render in any terminal.

The code points below are private-use-area glyphs from Nerd Fonts v3.
"""

from __future__ import annotations

# Icon kind -> Nerd Font glyph (private use area).
_NERD: dict[str, str] = {
    "folder": "\uf07b",  # nf-fa-folder
    "folder_open": "\uf07c",  # nf-fa-folder_open
    "file": "\uf15b",  # nf-fa-file
    "python": "\ue73c",  # nf-seti-python
    "javascript": "\ue74e",  # nf-seti-javascript
    "json": "\ue60b",  # nf-dev-json
    "markdown": "\ue73e",  # nf-seti-markdown
    "yaml": "\ue615",  # nf-seti-yml
    "toml": "\ue615",
    "html": "\ue736",  # nf-seti-html
    "css": "\ue749",  # nf-seti-css
    "rust": "\ue7a8",  # nf-seti-rust
    "go": "\ue626",  # nf-dev-go
    "bash": "\uf489",  # nf-fa-terminal
    "sql": "\ue706",
    "xml": "\ue619",  # nf-seti-xml
    "java": "\ue738",  # nf-seti-java
    "archive": "\uf1c6",  # nf-fa-file_archive_o
    "image": "\uf1c5",  # nf-fa-file_image_o
    "pdf": "\uf1c1",  # nf-fa-file_pdf_o
    "text": "\uf15b",  # nf-fa-file
    "lock": "\uf023",  # nf-fa-lock
}

# Plain-text fallbacks for terminals without a Nerd Font.
_TEXT: dict[str, str] = {
    "folder": "+",
    "folder_open": "-",
}

# File extension -> icon kind.
_EXTENSION_ICON: dict[str, str] = {
    "py": "python",
    "pyw": "python",
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "json": "json",
    "md": "markdown",
    "markdown": "markdown",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "html": "html",
    "htm": "html",
    "css": "css",
    "rs": "rust",
    "go": "go",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "fish": "bash",
    "sql": "sql",
    "xml": "xml",
    "java": "java",
    "zip": "archive",
    "tar": "archive",
    "gz": "archive",
    "xz": "archive",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "gif": "image",
    "svg": "image",
    "pdf": "pdf",
    "txt": "text",
}

VALID_MODES = ("nerd", "text")


def _glyph(kind: str, mode: str) -> str:
    if mode == "nerd":
        return _NERD.get(kind, "")
    return _TEXT.get(kind, "")


def folder(mode: str) -> str:
    """Icon for a collapsed directory."""
    return _glyph("folder", mode)


def folder_open(mode: str) -> str:
    """Icon for an expanded directory."""
    return _glyph("folder_open", mode)


def file_icon(filename: str, mode: str) -> str:
    """Icon for *filename* based on its extension (generic file when unknown)."""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        kind = _EXTENSION_ICON.get(ext)
        if kind is not None:
            return _glyph(kind, mode)
    return _glyph("file", mode)
