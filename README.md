# kvide

A small, safety-minded terminal code editor built on [Textual](https://textual.textualize.io/).
It is the first working version of a terminal IDE, intended to grow into a
client deeply integrated with the Kvist coding agent.

## Features

- Project file explorer (lazy-loaded directories, no full-tree scan)
- Tabbed multi-file editor with syntax highlighting (Python and other
  Tree-sitter languages)
- Line numbers, cursor movement, selection, copy/paste, undo/redo, auto-indent
- Unsaved-change tracking with a modified marker on the tab and in the status bar
- Safe close/quit: a prompt before discarding unsaved changes
- Quick file switcher (Ctrl+P) with fuzzy matching
- Nerd Font icons with a plain-text fallback mode
- Keyboard and mouse navigation — no Vim knowledge required

## Installation

Requires Python 3.12+.

```bash
git clone <this repository>
cd kvide
python -m venv .venv
source .venv/bin/activate
pip install -e ".[syntax]"     # syntax highlighting grammars
pip install -e ".[dev]"        # pytest, for running the test suite
```

The `syntax` extra installs the `tree-sitter-*` grammars that power
highlighting. Without it the editor still runs, but files are shown as plain
text.

## Running

```bash
kvide                 # open the current directory
kvide path/to/project
python -m kvide       # equivalent, without the console script
```

Options:

```text
--icons {nerd,text}   icon set (default nerd; use text without a Nerd Font)
--show-hidden         show hidden files and directories
```

For correct icons, install a Nerd Font (https://www.nerdfonts.com/) and set it
as the terminal font. Use `--icons text` otherwise.

## Keyboard shortcuts

| Keys | Action |
| --- | --- |
| `Ctrl+S` | Save the current file |
| `Ctrl+W` | Close the current tab |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Next / previous tab |
| `Ctrl+PageDown` / `Ctrl+PageUp` | Next / previous tab (terminal-safe alternative) |
| `Ctrl+P` | Quick file switcher |
| `Ctrl+Q` | Quit |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo (in the editor) |

The file tree supports `Up`/`Down`, `Enter` to open, `Left`/`Right` to
collapse/expand, and mouse clicks. Clicking a folder label toggles it.

## Architecture

The editing and file-handling logic is kept free of Textual widgets so it can
be tested without a terminal:

```
src/kvide/
  app.py        application lifecycle, wiring, commands (Textual App)
  editor.py     EditorArea: the TextArea view bound to a Document
  documents.py  Document + DocumentStore (pure Python, no Textual)
  workspace.py  filesystem operations and directory scanning (pure Python)
  textutil.py   newline detection/normalization (pure Python)
  languages.py  filename -> Tree-sitter language detection
  icons.py      Nerd Font glyphs with text fallbacks
  config.py     Settings from the command line
  screens.py    modal prompts and the quick file switcher
  theme.py      the Textual stylesheet
  widgets/      explorer (directory tree), status bar, header
```

`DocumentStore` owns open documents, dirty tracking and persistence; the
`TextArea` widgets are views that sync text into it on every change. The
`Workspace` class performs all filesystem access and reports failures as typed
exceptions instead of crashing the UI.

## Testing

```bash
python -m pytest
```

The suite covers newline handling, workspace/filesystem operations, the
document store, and end-to-end app behavior through Textual's headless pilot
(open, edit, save, switch tabs, close and quit with unsaved changes).

## Known limitations

- No LSP, Git integration, terminal emulation, plugin system, or AI agent
  execution (intentionally out of scope for this version).
- Syntax highlighting requires the `syntax` extra to be installed.
- Icons are best-effort Nerd Font code points; use `--icons text` if glyphs
  render as boxes.
- Ctrl+Tab may be intercepted by some terminals; Ctrl+PageDown/PageUp are
  provided as alternatives.
- Files are read and written as UTF-8 (with a latin-1 fallback on read).

## Next steps

The natural next step is a document/selection API surface that Kvist can drive
programmatically (open, edit, save, navigate), followed by Git integration.
