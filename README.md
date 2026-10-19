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
- Commit panel: select files, write a message, commit selected changes
- Optional commit-message generators (small pluggable scripts)
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
--generators FILE     optional commit-message generator config (TOML)
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
| `Ctrl+B` | Show the file explorer |
| `Ctrl+G` | Show the commit panel |
| `Ctrl+Q` | Quit |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo (in the editor) |

The file tree supports `Up`/`Down`, `Enter` to open, `Left`/`Right` to
collapse/expand, and mouse clicks. Clicking a folder label toggles it.

## Completion extensions

Run trusted JavaScript completion providers using a limited VS Code-compatible
API (Node.js required):

```bash
python -m kvide . --completion-extension examples/completion-extension
```

Type `pri` in a Python file or press `Ctrl+Space`; select with Up/Down and insert
with Tab/Enter. Escape dismisses. Extensions execute code with your permissions;
only enable trusted directories. CommonJS providers using the documented subset
can keep their `require('vscode')` and registration code. This is not full VS Code
extension compatibility. See [Completion extensions](docs/completions.md) for
installation, the API contract, TypeScript migration and limitations.

## Documentation

- [Completion extensions](docs/completions.md) — VS Code-style JavaScript API,
  installation, examples, supported surface and migration limitations.

- [Commit panel](docs/commit-panel.md) — selecting files, committing exactly
  those files, unsaved-buffer and merge-conflict checks, error reference.
- [Commit-message generators](docs/generators.md) — the TOML configuration,
  icon files, input and output protocol, JSON error notifications, examples and
  troubleshooting.

## Commit panel

`Ctrl+G` opens the commit panel and `Ctrl+B` returns to the file explorer (the
folder and git icons in the activity bar do the same). Inside the panel: `Space`
toggles a file, type a message, then press `Commit`. Only the selected files are
committed and unrelated staged changes are left alone. Unsaved editor buffers
must be saved first. There is no push. See
[docs/commit-panel.md](docs/commit-panel.md) for the full behaviour and error
reference.

## Message generators

Generators are optional scripts that write a commit message from the selected
diff. They are enabled explicitly:

```bash
kvide --generators generators.toml
```

Each entry becomes a button above the message field; `Ctrl+F1` through `Ctrl+F9`
trigger the first nine when the panel has focus. A generator reads one JSON
object from stdin (`version`, `files`, `diff`), prints the message as plain text
on success, and can print
`{"error": {"code": "...", "message": "..."}}` to raise a notification. See
[docs/generators.md](docs/generators.md) for the configuration format, the
icon file and the complete protocol. An optional `color = "#4fc3f7"` in a
generator entry colors only its icon (including `*` in `--icons text` mode),
not its name or shortcut. Omit it or use `color = ""` for the default appearance.

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
  git.py        selected-file staging and commit (pure Python)
  generators.py commit-message generator config and protocol (pure Python)
  screens.py    modal prompts and the quick file switcher
  theme.py      the Textual stylesheet
  widgets/      explorer, commit panel, status bar, header
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
document store, selected-file Git operations, the generator protocol, and
end-to-end app behavior through Textual's headless pilot (open, edit, save,
switch tabs, close and quit with unsaved changes, commit and generation in the
commit panel).

## Known limitations

- No LSP, terminal emulation, or AI agent execution (intentionally out of
  scope for this version). Git support is limited to committing selected files:
  no push, branching, or history view.
- Syntax highlighting requires the `syntax` extra to be installed.
- Icons are best-effort Nerd Font code points; use `--icons text` if glyphs
  render as boxes.
- Ctrl+Tab may be intercepted by some terminals; Ctrl+PageDown/PageUp are
  provided as alternatives.
- Files are read and written as UTF-8 (with a latin-1 fallback on read).

## Next steps

The natural next step is a document/selection API surface that Kvist can drive
programmatically (open, edit, save, navigate), followed by fuller Git support
(branching, push, a history view).

## LICENSE
MIT



