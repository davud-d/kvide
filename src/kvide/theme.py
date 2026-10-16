"""The application stylesheet (Textual CSS)."""

from __future__ import annotations

APP_CSS = """
Screen {
    layout: vertical;
    background: $surface;
}

#header {
    height: 1;
    background: $panel;
    color: $text;
    padding: 0 1;
}

#body {
    height: 1fr;
}

#explorer {
    width: 34;
    background: $surface-darken-1;
    border-right: solid $primary-background;
    padding: 0 1;
}

#tabs {
    width: 1fr;
}

#status {
    height: 1;
    background: $panel;
    color: $text-muted;
    padding: 0 1;
}

EditorArea {
    padding: 0 0 0 1;
    background: $surface;
}

ConfirmScreen, QuickSwitchScreen {
    align: center middle;
}

#confirm-box, #quick-box {
    width: 64;
    height: auto;
    max-height: 24;
    background: $panel;
    border: round $primary;
    padding: 1 2;
}

#confirm-box Label {
    width: 100%;
    padding: 1 0;
}

#confirm-buttons {
    height: auto;
    padding: 0 0 1 0;
}

#confirm-buttons Button {
    margin-right: 1;
}

#quick-input {
    width: 100%;
    margin-bottom: 1;
}

#quick-list {
    width: 100%;
    height: auto;
    max-height: 18;
}
"""
