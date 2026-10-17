# Commit panel

The commit panel is kvide's Git surface. It lists the changed files of the open
repository, lets you select the ones to include, writes a commit message and
creates one commit from exactly those files. It does not push, amend, switch
branches or show history.

This document describes the panel as implemented. For the optional
message-generation scripts, see [generators.md](generators.md).

## Opening and closing

| Action | How |
| --- | --- |
| Open the commit panel | `Ctrl+G`, or the git icon in the activity bar |
| Return to the file explorer | `Ctrl+B`, or the folder icon in the activity bar |

The activity bar sits on the left edge of the window. In `nerd` icon mode the
folder button shows the folder glyph (U+F07C) and the commit button the git
glyph (U+E729); in `text` mode they are the letters `F` and `G`. Both buttons
have tooltips with their shortcut.

The panel and the explorer share the same column, so opening one hides the
other. Opening the panel triggers a fresh `git status`, so changes made in an
external editor show up without pressing `Refresh`.

Hiding the panel does **not** throw away state. The selected files and the
message draft stay in memory, and returning to the panel shows them again. The
file list is refreshed on every open, and selections are kept for paths that are
still changed.

## Layout

From top to bottom:

1. The title `Commit`.
2. A hint line: `Select saved files. Space toggles a file.`
3. The list of changed files.
4. A status line (`3 changed file(s)`, `No changes. Save a file, then Refresh.`,
   or the current error).
5. Optional generator buttons, one per configured generator (see
   [generators.md](generators.md)), in a scrollable strip.
6. The label `Commit message` and a multiline text field.
7. The buttons `Commit` and `Refresh`.

The list itself shows, for every entry, the two-character Git status from
`git status --porcelain`, in `nerd` mode a file-type icon, and the
repository-relative path. For a rename, the path shown is the new one. Examples
of statuses:

| Status | Meaning |
| --- | --- |
| `??` | untracked file |
| ` M` | modified in the working tree, not staged |
| `M ` | staged modification |
| `MM` | staged and then modified again |
| `A ` | staged new file |
| ` D` | deleted in the working tree, not staged |
| `D ` | staged deletion |
| `R ` | staged rename |

The panel shows the whole change set, not only what is staged. Staged and
unstaged changes to the same file appear as one row whose status reflects both.

## Selecting files

- `Up` / `Down` move the highlight. Clicking a row highlights it.
- `Space` toggles the highlighted file. `Space` on a highlighted row is the
  normal way to add or remove it from the commit.
- The selection is a set; files can be selected in any order.
- The `Commit` button stays disabled until at least one file is selected and the
  message field contains non-whitespace text.

Selecting a file does not stage it immediately. Staging happens as part of
committing, so an abandoned selection leaves the index untouched.

## Writing the message

Type into the field under `Commit message`. It is a plain multiline text field
with soft wrapping; `Enter` inserts a newline. There is no subject/body split
and no length limit imposed by kvide. The text is passed to Git as the message
file for `git commit --file=-`.

The draft survives hiding the panel and survives a failed commit. It is cleared
only after a successful commit.

A generator can replace the draft with a generated message, but never commits on
its own. After generating, review the text and press `Commit` yourself.

## Committing

Pressing `Commit` runs, in order:

1. A check that at least one file is selected.
2. A check that the message is not empty or whitespace.
3. A fresh `git status` comparison; if any selected change no longer exists
   with the same status and paths, the commit is refused with
   `Changes have moved. Refresh and select files again.`
4. A merge-conflict check. Unmerged paths (`DD`, `AU`, `UD`, `UA`, `DU`, `AA`,
   `UU`) are refused with `Resolve merge conflicts before committing.`
5. A path check rejecting absolute paths and paths containing `..`.
6. `git add --all -- <paths>` for the selected paths that still exist in the
   working tree. Deleted paths and the source path of a rename are skipped here.
7. `git commit --only --file=- -- <paths>`, with the message on stdin.

The `--only` form is what keeps the commit scoped: the named paths are committed
from their current working-tree content, while unrelated entries that were
already in the index are **not** included and remain staged afterwards.

Consequences worth knowing:

- **Unsaved editor buffers are not committed.** Git can only commit file
  content on disk. If a selected file is open in kvide with unsaved changes,
  the commit is refused with `Save selected files before committing.` Save each
  dirty selected file with `Ctrl+S` first. This check covers both the new path
  and the original path of a rename.
- **Deletions are committed.** A deleted tracked file is passed to
  `git commit --only` without a preceding `git add`; Git records the deletion.
- **Renames are committed as renames.** Both the old and the new path are
  passed to `git commit --only`; only the new path is passed to `git add`.
- **An initial commit works.** In a repository with no `HEAD` yet, the selected
  files are added and committed normally.
- **Git hooks run.** Client-side hooks (for example `pre-commit` and
  `commit-msg`) execute as usual and can reject the commit. Their message is
  shown in the notification.
- **Signing, templates and other Git configuration apply.** kvide does not pass
  flags that disable hooks or signing; it uses the user's Git configuration.
- **Nothing is pushed.** There is no remote operation in the panel.

On success, kvide shows Git's own output as a notification (for example
`[master 1a2b3c4] Add commit panel`), clears the message field and reloads the
change list. The committed files disappear from the list unless they still have
unstaged changes.

On failure, the error is shown as an error notification, the message draft is
kept and the panel status says
`Commit failed. Draft kept; selected files may be staged.` This is accurate:
the `git add` in step 6 has already run, so a file can be staged even though no
commit was created.

## Refreshing

`Refresh`, or reopening the panel with `Ctrl+G`, reloads `git status`. Use it
after saving files in kvide, after running Git commands in a terminal, or after
a commit failed because the change set moved.

The panel also reloads automatically after every successful commit. While a
reload or a commit is running, the list, the message field and all buttons are
disabled; after a reload the list is refocused.

## Errors and what they mean

| Message | Cause | Fix |
| --- | --- | --- |
| `Open the Git repository root to commit changes.` | The workspace directory is inside a repository but is not its top level. | Start kvide with the repository root, for example `kvide .` from the root. |
| `Select at least one file.` | Commit was attempted with an empty selection. | Select a file. |
| `Enter a commit message.` | The message is empty or whitespace only. | Type a message. The button is normally disabled in this state. |
| `Changes have moved. Refresh and select files again.` | A selected file changed status or disappeared since the list was loaded. | Press `Refresh`, select again. |
| `Resolve merge conflicts before committing.` | A selected path is unmerged. | Resolve the conflict in the working tree and stage the result. |
| `Save selected files before committing.` | A selected file has unsaved changes in the editor. | `Ctrl+S` in each editor tab, then commit again. |
| `Invalid repository path.` | Git reported an absolute path or a path with `..`. | Refresh; if it persists, commit from the terminal to inspect the index. |
| `Git could not finish: ...` | The `git` executable is missing or the command timed out (30 s for status, 120 s for commit). | Check that Git is installed and responsive. |
| Any other text | Git's own `stderr`, for example a missing `user.name`, a hook rejection or an empty commit. | Follow Git's message; kvide passes it through unchanged. |

Git is executed with `GIT_TERMINAL_PROMPT=0`, so a repository that wants
credentials fails instead of waiting for input. Committing does not contact a
remote, but hooks may.

## Limits

- The workspace must be the repository root; opening a subdirectory of a
  repository does not work for commits.
- One commit at a time; there is no staging-area editor, no partial-line or
  hunk staging.
- No push, pull, fetch, branch, tag, amend, reset or history view.
- Untracked files are listed individually (`--untracked-files=all`), including
  files inside untracked directories.
- Ignored files are not listed, because Git does not report them.
- File content shown in the diff sent to generators follows the rules in
  [generators.md](generators.md); the commit itself uses whatever is on disk.

## Keyboard reference

| Keys | Action |
| --- | --- |
| `Ctrl+G` | Open the commit panel and refresh |
| `Ctrl+B` | Return to the file explorer |
| `Up` / `Down` | Move in the file list |
| `Space` | Toggle the highlighted file |
| `Ctrl+F1` … `Ctrl+F9` | Run the corresponding generator (panel focused, files selected) |
| `Escape` | Return to the file explorer while focus is in the panel |
