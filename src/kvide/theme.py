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

#activity-bar {
    width: 5;
    background: $panel;
    border-right: solid $primary-background;
}

#activity-bar Button {
    min-width: 3;
    width: 3;
    height: 3;
    padding: 0;
    border: none;
    background: $panel;
    color: $text;
}

#activity-bar Button.active {
    background: $primary-background;
    text-style: bold;
}

#activity-bar Button:focus {
    border: tall $primary;
}

#commit-panel {
    width: 34;
    background: $surface-darken-1;
    border-right: solid $primary-background;
    padding: 0 1;
}

#commit-title {
    height: 1;
    text-style: bold;
}

#commit-hint {
    height: 2;
}

#commit-files {
    height: 1fr;
    min-height: 3;
    border: none;
}

#commit-state {
    height: 2;
}

#generator-tools {
    height: auto;
    max-height: 3;
}

.generator-button {
    width: 100%;
    height: 1;
    min-height: 1;
    border: none;
    text-align: left;
    padding: 0;
}

.generator-button:focus {
    text-style: reverse;
}

#message-label {
    height: 1;
}

#commit-message {
    height: 5;
    border: solid $primary-background;
}

#commit-message:focus {
    border: solid $primary;
}

#commit-actions {
    height: 3;
}

#commit-actions Button {
    min-width: 10;
    margin-right: 1;
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
