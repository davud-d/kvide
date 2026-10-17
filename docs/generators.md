# Commit-message generators

A generator is an external program that reads the selected changes and writes a
commit message. Generators are optional: kvide runs only the ones listed in a
trusted TOML file supplied with `--generators` or in the user configuration.

A generator can be a local script, a wrapper around a model API, or anything
else that can read JSON from stdin and write text to stdout. kvide does not care
what language it is written in.

This document is the reference for the configuration format, the icon file, the
exact input and output contract, and the behaviour of the panel around a
generation run. For the panel itself, see [commit-panel.md](commit-panel.md).

## Quick start

`generators.toml`:

```toml
[[generators]]
name = "Local"
command = ["python", "/home/me/.config/kvide/local-generator.py"]
icon = "local-icon.txt"
timeout = 60
```

`local-icon.txt` holds a single glyph and a trailing newline. For the Nerd Font
terminal icon the file contains the one character U+F489.

`local-generator.py`:

```python
#!/usr/bin/env python3
"""Write a commit message for the changes passed on stdin."""

import json
import sys

context = json.load(sys.stdin)
files = ", ".join(context["files"])
print(f"Update {files}")
```

Start kvide with the configuration:

```bash
kvide --generators generators.toml
```

Open the commit panel (`Ctrl+G`), select at least one file, then click the
`Local` button or press `Ctrl+F1`. The generated text appears in the message
field. Review it and press `Commit` yourself; generation never commits.

## Enabling generators

```text
kvide --generators FILE     # path to a TOML configuration
```

Configuration is selected in this order:

1. `--generators FILE` takes precedence and disables the user default entirely,
   even if FILE is missing or invalid. The files are never merged. Relative
   explicit paths are resolved from the directory kvide was started from.
2. Without the flag, kvide reads `$XDG_CONFIG_HOME/kvide/generators.toml`, or
   `~/.config/kvide/generators.toml` if XDG_CONFIG_HOME is unset, empty or relative.
   On Windows it uses `%APPDATA%\kvide\generators.toml` instead; if APPDATA is
   unset, empty or relative, there is no default. Only an existing path is loaded.
3. If the user file does not exist, no generators are loaded and no error is shown.

- kvide never searches the repository or working directory for a configuration.
- The configuration is read once at startup. Editing the TOML or the icon file
  requires restarting kvide.
- The configuration file is trusted input. Every command in it is executed
  with your user's privileges (see [Security](#security)).

If the file cannot be read or parsed, kvide still starts, shows one error
notification at startup and runs without generators. A single invalid entry
rejects the whole file; the valid entries are not loaded partially.

## Configuration reference

The file is TOML. The key kvide reads is `generators`, an array of tables
(`[[generators]]`). Entries are loaded in file order, and that order is the
order of the buttons in the panel.

```toml
[[generators]]
name = "Local"
command = ["python", "/path/to/plugin.py"]
icon = "icon.txt"
timeout = 60

[[generators]]
name = "Remote"
command = ["/usr/bin/my-remote-generator", "--model", "small"]
timeout = 120
```

| Key | Type | Required | Rules |
| --- | --- | --- | --- |
| `name` | string | yes | Non-empty after trimming surrounding whitespace. Shown on the button, in status text and in error notifications. |
| `command` | array of strings | yes | Non-empty array; every element must be a non-empty string. Executed directly, without a shell. |
| `icon` | string | no | Path to a small text file containing the button glyph. Defaults to `*`. See [Icons](#icons). |
| `color` | string | no | Icon color accepted by Rich, for example `"#4fc3f7"` or `"cyan"`. Omitted or empty means no custom color. |
| `timeout` | integer | no | Seconds, from 1 to 300. Defaults to 60. |

Unknown keys are ignored, so a configuration may carry extra fields for other
tools.

### `command` is not a shell string

`command` is passed to the operating system as an argument vector. Shell syntax
is not interpreted: `["python plugin.py"]` looks for an executable literally
named `python plugin.py` and fails. Use separate elements:

```toml
command = ["python", "plugin.py"]
```

Redirection, pipes, `&&`, `$VAR` expansion and glob patterns do not work. If you
genuinely need shell features, start a shell explicitly:

```toml
command = ["sh", "-c", "my-generator --flag | head -n 20"]
```

The working directory is the repository root, so relative command paths are
resolved against it, not against the TOML file. Prefer absolute paths for both
the interpreter and the script to avoid surprises, or a command found on `PATH`
such as `python` or `uv`.

### Timeouts

The timeout covers the whole process, from start to exit. When it expires kvide
kills the process and reports an error. It is not a per-read timeout, and a
generator that finishes just under the limit but prints a large response still
has to pass the output checks.

`1` is the minimum useful value and `300` the maximum. A remote model call
usually needs more than the 60-second default; set `120`–`300` for those.

## Icons

Each generator can show a glyph on its button. The glyph lives in its own small
text file, not in the TOML, so a Nerd Font code point can be pasted and edited
without escaping.

```toml
icon = "local-icon.txt"   # relative to the TOML file
# icon = "/home/me/.config/kvide/icons/model.txt"   # absolute also works
```

The icon file:

- is read as UTF-8 (with kvide's latin-1 fallback),
- is trimmed of surrounding whitespace, including the trailing newline,
- must contain **1 to 4 characters** after trimming,
- must not contain control characters (tab, carriage return, escape and the
  rest are rejected),
- is re-read only at startup.

Any failure to read the file, or an invalid glyph, rejects the whole generator
configuration with a notification such as
`Cannot load generators: cannot read: /path/icon.txt`.

To get a glyph, open the [Nerd Fonts cheat sheet](https://www.nerdfonts.com/cheat-sheet),
copy the character and paste it into the file. Keep the terminal font set to a
Nerd Font, otherwise the glyph renders as a box or a question mark. A plain
text file with a letter or emoji also works, subject to the 1–4 character limit
and the terminal font.

In `--icons text` mode the configured icon is not used: every generator button
shows `*` so the panel stays readable without a Nerd Font. The icon file is
still validated at startup.

If `icon` is omitted or set to an empty string, the button uses `*`.

Set an optional color in the generator's TOML entry:

```toml
color = "#4fc3f7"
```

Only the icon is colored; the name and shortcut keep their existing appearance.
The color also applies to `*` in `--icons text` mode or when no icon is set.
Omitting `color` or setting it to `""` keeps the previous uncolored label.
Colors are validated with `rich.color.Color.parse`; a non-string or invalid
color rejects the whole configuration at startup.

## Where generator buttons appear

The buttons form a scrollable strip between the panel status line and the
message field. Each label is:

```text
<icon> <name>  Ctrl+F<n>
```

The shortcut suffix is shown and bound only for the first nine generators
(`Ctrl+F1` through `Ctrl+F9`). Additional generators still get buttons and can
be clicked; they have no keyboard shortcut.

A run starts when you click a button or press its shortcut. All of these must
hold, otherwise nothing happens or a warning is shown:

| Condition | If it does not hold |
| --- | --- |
| The commit panel is visible | The shortcut does nothing; the editor keeps focus. |
| Focus is inside the commit panel | The shortcut does nothing. |
| No modal dialog is open | The shortcut does nothing; a confirmation prompt keeps its keys. |
| No commit, refresh or generation is already running | The shortcut does nothing; buttons are disabled. |
| The change list has loaded | The shortcut does nothing. |
| At least one file is selected | A warning notification: `Select files before generating a message.` |

Generators do not run while the file explorer is shown, from the editor, or
while a modal screen is on top. This is deliberate: an accidental `Ctrl+F1`
while editing must not start a remote request.

Some terminals intercept function keys. If `Ctrl+F1` does not reach kvide, the
button click is the reliable path.

## Input contract

kvide writes one JSON object to the generator's stdin and closes stdin. The
object has exactly three keys:

```json
{
  "version": 1,
  "files": ["src/kvide/git.py", "docs/generators.md"],
  "diff": "diff --git a/src/kvide/git.py b/src/kvide/git.py\n..."
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `version` | integer | Protocol version. Currently always `1`. Check it if your generator must support future versions. |
| `files` | array of strings | Repository-relative paths of the selected changes, in the order they appear in the panel. For a rename this is the new path; for a deletion, the deleted path. |
| `diff` | string | A text diff of the selected changes. See below. |

The JSON uses ordinary `json.dumps` formatting; whitespace is not significant.
Parse it as JSON rather than by pattern. The object is not followed by a newline
or any other data.

### How the diff is built

For every selected change, kvide collects one block and joins the blocks with a
single newline:

- **Untracked file (`??`)** — no Git diff exists, so the block is the literal
  line `New file: <path>` followed by the file's full text:

  ```text
  New file: notes/todo.md
  # Todo
  ...
  ```

- **Tracked change** — the output of
  `git diff HEAD --no-ext-diff --no-textconv -- <paths>`.
  `--no-ext-diff` disables external diff drivers, `--no-textconv` disables
  binary-to-text filters, so the generator receives ordinary patch text.
- **Repository without `HEAD`** — for an initial commit there is nothing to
  compare against, so kvide uses
  `git diff --cached --no-ext-diff --no-textconv -- <paths>` instead.

For a rename, both the old and the new path are passed to Git; the diff then
contains the rename metadata as Git prints it. For a deletion, the diff shows
the removed lines.

The diff can be empty for a change that has no textual content difference, for
example a pure mode change. Generators must handle an empty `diff` string.

### Limits and exclusions

- **1 MB diff limit.** If the UTF-8 encoded diff exceeds 1,000,000 bytes,
  nothing is sent and the notification says
  `Selected diff exceeds the generator limit (1 MB). Select fewer files.`
- **Credential paths are refused.** If any selected path contains a component
  starting with `.env`, a component equal to `.ssh`, `.aws` or `.gnupg`, or has
  the suffix `.pem`, `.key`, `.p12`, `.pfx`, `.crt` or `.cer` (case-insensitive),
  generation is refused with
  `Credential files cannot be sent to a generator.`
  Deselect those files to continue. This check applies only to generation; the
  commit itself can still include such files if they are tracked.
- **Freshness check.** Before building the diff, kvide re-reads `git status`.
  If the selected change set has moved, generation fails with
  `Changes have moved. Refresh and select files again.` Refresh the panel and
  select again.
- **Merge conflicts.** Unmerged paths are refused, as in the commit path, with
  `Resolve merge conflicts before committing.`
- **No secrets scanning beyond paths.** The diff is sent as-is. If a file
  contains a token in its content, kvide does not detect it. Use local
  generators for material you would not send to a third party.

### Process environment

| Property | Value |
| --- | --- |
| Working directory | Repository root (the kvide workspace) |
| Environment | Inherited from kvide unchanged |
| stdin | The JSON object, then EOF |
| stdout | Captured and interpreted as the response |
| stderr | Captured but ignored by kvide |
| Timeout | `timeout` from the configuration, 1–300 seconds, default 60 |
| Shell | None; the command is executed directly |

Because stderr is ignored, a traceback printed there will not be shown. Report
user-facing failures through the JSON error envelope below, or write diagnostics
to a log file.

## Output contract

The response is read from stdout after the process exits. If the timeout
expires, the process is killed and an error is reported instead. The whole
stdout is captured; there is no streaming and no partial message.

### Success: plain text

Print the commit message as plain text. kvide trims surrounding whitespace and
uses the rest verbatim as the message field content. Newlines inside the text
are kept, so a subject line and a body work:

```text
Add commit panel

The panel lists changed files, commits only the selected ones
and keeps unrelated staged changes out of the commit.
```

The success response must satisfy all of these:

| Rule | Violation |
| --- | --- |
| Non-empty after trimming | `empty or invalid message` |
| At most 16,000 characters | `response exceeds 16000 characters` |
| No control characters except newline (`\n`) and tab (`\t`) | `empty or invalid message` |
| Exit code 0 | `exited with code N` |

The 16,000-character limit applies to the stdout text, not to the resulting
commit. A carriage return (`\r`) counts as a control character; convert Windows
line endings to `\n` before printing.

A JSON string such as `"Update a.py"` is not special-cased: because it parses to
a string rather than an object, it is treated as literal text and the quotes end
up in the message. Print unquoted text.

### Failure: JSON error envelope

To show a proper notification, print a single JSON object with an `error` field:

```json
{"error": {"code": "insufficient_funds", "message": "Top up the account."}}
```

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `error` | object | yes | Marks the response as an error. |
| `error.code` | string | no | Machine-readable identifier, for example `insufficient_funds`, `overloaded`, `rate_limited`. Defaults to `error` in the notification text. |
| `error.message` | string | yes | Human-readable explanation. This is what the user reads. |

The notification is shown with severity `error` and with markup disabled, so
characters such as `[` and `]` are displayed literally. The text is formatted as:

```text
<generator name>: <code>: <message>
```

For the example above with a generator named `Remote`:

```text
Remote: insufficient_funds: Top up the account.
```

`code` is yours to define. kvide does not interpret it and has no fixed
vocabulary; choose short stable identifiers and put the explanation in
`message`. Keep the message actionable and free of secrets.

A JSON error envelope takes precedence over the exit code: printing the envelope
and exiting with status 1 still produces the notification described above
rather than an exit-code error. You can therefore use `sys.exit(1)` after
printing the envelope, which is the conventional behaviour.

### Invalid responses

| stdout | Exit code | Result |
| --- | --- | --- |
| plain text | 0 | Success; text becomes the message. |
| plain text | non-zero | Error `<name>: exited with code N`; text is not applied. |
| JSON object with valid `error.message` | any | Error `<name>: <code>: <message>`. |
| JSON object without a valid `error` object | any | Error `<name>: expected plain text or a JSON error`. |
| empty or whitespace only | 0 | Error `<name>: empty or invalid message`. |
| over 16,000 characters | any | Error `<name>: response exceeds 16000 characters`. |
| JSON array, number, boolean or string | 0 | Treated as plain text (string quotes included). |
| process cannot start | — | Error with the underlying operating-system message. |
| timeout | — | Error naming the generator and the timeout failure. |

The `"expected plain text or a JSON error"` case is the usual one when a
generator prints a JSON success envelope such as `{"message": "..."}`: kvide
expects either bare text or an `error` object, not a general-purpose JSON
document.

## What happens in the panel

1. kvide records the current draft, marks the panel busy and disables every
   button, the file list and the message field.
2. It validates the selection and builds the input in a worker thread, so the
   interface stays responsive.
3. It runs the generator in a worker thread with the configured timeout.
4. On success, the generated text replaces the message **only if the draft has
   not changed since the run started**. This prevents a slow generator from
   overwriting text you typed meanwhile. If the draft did change, the result is
   discarded and the status line says
   `Draft changed; generated message was not applied.`
5. On success with an unchanged draft, the status line says
   `Message generated. Review it, then press Commit.` Nothing is committed.
6. On any error, an error notification is shown, the draft is left untouched and
   the status line says `Generation failed. Your draft is unchanged.`
7. The panel becomes idle again and all controls are re-enabled.

Generation replaces the draft rather than appending to it. If you want to keep
an existing draft, do not run a generator over it; the panel does not offer a
merge or "insert at cursor" mode.

There is no cancel button. A running generator blocks other panel actions until
it exits or hits its timeout. Keep timeouts modest for scripts that may hang.

## Examples

### Minimal: derive a subject from the file list

```python
#!/usr/bin/env python3
import json
import sys

context = json.load(sys.stdin)

if context.get("version") != 1:
    print(json.dumps({
        "error": {
            "code": "unsupported_version",
            "message": f"Unsupported protocol version: {context.get('version')!r}",
        }
    }))
    sys.exit(1)

files = context["files"]
subject = files[0] if len(files) == 1 else f"{len(files)} files"
print(f"Update {subject}")
```

### Local heuristics over the diff

```python
#!/usr/bin/env python3
import json
import sys

context = json.load(sys.stdin)
diff = context["diff"]
files = context["files"]

if not diff.strip():
    print(f"Touch {', '.join(files)}")
    sys.exit(0)

added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))

if added > removed * 3:
    verb = "Add"
elif removed > added * 3:
    verb = "Remove"
else:
    verb = "Update"

print(f"{verb} {', '.join(files)}")
```

### Mapping HTTP failures to notifications

The following is a sketch for a remote generator. It is illustrative; adapt the
endpoint, request body and error mapping to your service.

```python
#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request

def fail(code: str, message: str) -> None:
    print(json.dumps({"error": {"code": code, "message": message}}))
    sys.exit(1)

context = json.load(sys.stdin)
request = urllib.request.Request(
    "https://example.invalid/generate",
    data=json.dumps(context).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(request, timeout=90) as response:
        message = response.read().decode("utf-8").strip()
except urllib.error.HTTPError as exc:
    if exc.code == 402:
        fail("insufficient_funds", "Top up the account.")
    if exc.code == 429:
        fail("rate_limited", "Too many requests. Try again in a minute.")
    if exc.code >= 500:
        fail("overloaded", "The server is overloaded. Try again later.")
    fail("http_error", f"The service returned HTTP {exc.code}.")
except urllib.error.URLError as exc:
    fail("unreachable", f"Cannot reach the service: {exc.reason}")

if not message:
    fail("empty_response", "The service returned an empty message.")
print(message)
```

Note the two layers: HTTP and transport errors become the JSON envelope, while a
successful response is printed as bare text. Set the TOML timeout above the
generator's own HTTP timeout, for example `timeout = 120` for a 90-second HTTP
timeout, so kvide's kill does not pre-empt a useful error from the script.

### Several generators

```toml
[[generators]]
name = "Conventional"
command = ["python", "/home/me/.config/kvide/conventional.py"]
icon = "/home/me/.config/kvide/icons/commit.txt"
timeout = 30

[[generators]]
name = "Model"
command = ["/home/me/.config/kvide/model-generator"]
timeout = 240
```

The buttons appear in this order: `Conventional` is `Ctrl+F1`, `Model` is
`Ctrl+F2`. The second entry has no icon and shows `*`.

## Debugging a generator

Run it outside kvide with a captured input. In a repository with changes:

```bash
git status --porcelain
printf '%s' '{"version":1,"files":["README.md"],"diff":"diff --git a/README.md b/README.md\n..."}' \
  | python /path/to/plugin.py
echo "exit: $?"
```

Check three things separately: the exit code, whether stdout is plain text (not
a JSON success document), and whether stderr contains the real error. kvide
ignores stderr, so a script that prints its traceback there and an empty stdout
will only produce `empty or invalid message`.

For a remote generator, log request status codes and response bodies to a file
outside the repository while debugging. Do not print debug output to stdout: it
becomes part of the commit message.

## Security

- A generator is arbitrary code. It runs as your user, with your environment,
  your filesystem access and your network. There is no sandbox.
- The configuration is trusted input. The default lives in your home directory
  (`~/.config/kvide/generators.toml`), or your user configuration directory selected
  by XDG_CONFIG_HOME or Windows APPDATA. kvide never discovers configurations in
  a repository or working directory, so cloning a project cannot add a generator
  by itself. Review both your user configuration and files passed explicitly with
  `--generators`. File permissions are not checked.
- Selected diffs, including the full content of untracked files, are sent to the
  generator. Path-based credential exclusions (`.env*`, `.ssh`, `.aws`,
  `.gnupg`, key and certificate suffixes) are applied before the diff is built,
  but content is not scanned for secrets. Use a local generator for anything
  that must not leave the machine.
- The 1 MB diff cap limits accidental bulk uploads, not disclosure.
- kvide does not pass any API key or credential to the generator; if it needs
  one, it reads it from its own environment or configuration.
- Generation is not a commit. A malicious or wrong message still has to be
  reviewed and committed by you.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| No generator buttons | No configuration selected, or it lists no generators | Create the user configuration or pass `--generators FILE`. |
| No buttons, one error notification at startup | Configuration or icon file could not be read or parsed | Read the notification; it includes the underlying TOML or filesystem error. |
| `Cannot load generators: 'name'` (or `'command'`) | A required key is missing | Add `name` and `command` to every entry. |
| `Cannot load generators: command must be a nonempty array of strings` | `command` is a shell string or contains a non-string | Use `["python", "plugin.py"]`. |
| `Cannot load generators: timeout must be between 1 and 300 seconds` | Timeout out of range or not an integer | Use a whole number in `[1, 300]`. |
| `Cannot load generators: icon must contain 1–4 printable characters` | Icon file is empty, has a trailing escape sequence, or is too long | Put a single glyph and a newline in the file. |
| `Cannot load generators: ... is not a valid color` | `color` is not accepted by Rich | Use a color such as `"#4fc3f7"` or `"cyan"`, or omit it. |
| `Cannot load generators: color must be a string` | `color` has a non-string TOML type | Quote the color value; use `""` for no custom color. |
| Button shows `*` | `--icons text` mode, or no `icon` configured | Use a Nerd Font and the default `nerd` mode, and set `icon`. |
| Icon renders as a box | Terminal font is not a Nerd Font | Install a Nerd Font or use `--icons text`. |
| `Ctrl+F1` does nothing | Panel hidden, focus outside it, modal open, busy, or the terminal intercepts the key | Open the panel, click the button instead. |
| `Select files before generating a message.` | Nothing is selected in the file list | Select at least one change. |
| `Credential files cannot be sent to a generator.` | A selected path looks like a credential path | Deselect it. |
| `Selected diff exceeds the generator limit (1 MB).` | Too much changed content | Select fewer files. |
| `Changes have moved. Refresh and select files again.` | Files changed on disk since the panel loaded | Press `Refresh` and reselect. |
| `<name>: exited with code N` | The script printed plain text but returned a failure status | Make the script exit 0 on success, or print a JSON error envelope. |
| `<name>: expected plain text or a JSON error` | stdout is a JSON object that is not an error envelope | Print bare text on success, or use `{"error": {...}}`. |
| `<name>: empty or invalid message` | Empty stdout, control characters, or CRLF output | Print non-empty text with `\n` newlines. |
| `<name>: response exceeds 16000 characters` | The message is too long | Shorten the generated text. |
| Timeout error after N seconds | The generator hung or the remote call is slower than `timeout` | Raise `timeout`, add an HTTP timeout below it, and handle failures in the script. |
| Message field unchanged after a run | The draft was edited while the generator ran | Run again without typing, or accept that the draft has priority. |
| Traceback not shown in kvide | stderr is ignored | Log to a file or return the error as JSON. |

## Contract checklist

Before wiring a generator into kvide, verify:

- [ ] The executable and every argument are separate `command` elements.
- [ ] The script reads one JSON object from stdin and does not wait for more.
- [ ] `version`, `files` and `diff` are read as JSON fields, not parsed with
      regular expressions; an empty `diff` is handled.
- [ ] Success prints a non-empty plain-text message to stdout and exits 0.
- [ ] Failure prints `{"error": {"code": "...", "message": "..."}}`; the message
      is human-readable and contains no secrets.
- [ ] Nothing is written to stdout except the message or the error envelope.
- [ ] The script finishes within its configured timeout.
- [ ] The icon file holds 1–4 printable characters if an icon is configured.
