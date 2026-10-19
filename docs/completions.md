# Completion extensions

kvide runs JavaScript completion providers through a **limited VS Code API
compatibility layer**, not the full VS Code extension host. Providers using only
the API below can retain their `require('vscode')`, `activate(context)` and
`registerCompletionItemProvider` code. Arbitrary Marketplace extensions are not
compatible automatically. There is no VSIX installer, Marketplace downloader,
LSP client, Electron, or VS Code UI emulation.

## First completion

Install kvide as described in the README and install Node.js (18 or newer) using
your system package manager. Node is optional unless extensions are enabled.
From this repository, run:

```bash
python -m kvide . --completion-extension examples/completion-extension
```

Open a `.py` file and type `pri`. After a 250 ms pause, the completion list shows
`print`, its detail and documentation. `Ctrl+Space` explicitly requests suggestions.
Use Up/Down to select, Tab or Enter to insert, Escape to dismiss. Mouse selection
is also supported. The list stays near the cursor and is constrained by the
terminal bounds. Documentation is displayed as plain text, including Markdown
source; no HTML or links are executed. Insertion changes the unsaved buffer only;
Ctrl+Z undoes it and Ctrl+S saves normally.

The bundled example is a real CommonJS completion extension with a package.json;
it does not need npm dependencies or a build. It is a demonstration provider,
not a Python semantic engine. kvide supplies no language intelligence by itself.

## Trust and installation

`--completion-extension DIR` is repeatable. Each directory must contain a
`package.json` with a `main` field pointing to a compiled CommonJS JavaScript
entry point. Relative directory arguments resolve from the shell's working
directory, not the project directory passed to kvide. No project directory is
scanned or executed automatically. Extensions activate lazily on the first
request, regardless of their `activationEvents` manifest field.

**Only enable code you trust.** A separate Node process is crash isolation, not
a security sandbox. Extensions and their dependencies have your normal file,
process, environment and network privileges. kvide does not install dependencies,
run npm scripts, fetch code, or ask extensions to modify your project. Extension
code can still do all of those things itself. Review it before enabling it.
Stop loading an extension by removing its CLI argument and restarting kvide.

For an existing extension:

1. Copy or unpack its source/build directory to a location you control.
2. Read its entry point and check all `vscode` API calls against the table below.
3. Build TypeScript to CommonJS JavaScript using that extension's normal build
   process; kvide does not compile `.ts` files. Keep its runtime dependencies
   next to its package in `node_modules`. Review dependency installation scripts.
4. Pass the directory to `--completion-extension`. Test its providers with real
   documents. Unsupported APIs report an error rather than silently pretending
   to work.

For providers bundled with unrelated UI features, make a small separate entry
point that exports `activate` and registers only the providers. Dependencies on
`vscode-languageclient`, commands, configuration, events or filesystem watchers
need adaptation; copying those extensions unchanged is not supported.

## Provider contract

```javascript
const vscode = require('vscode');
exports.activate = context => {
    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider('python', {
            async provideCompletionItems(document, position, token, context) {
                const item = new vscode.CompletionItem('print', vscode.CompletionItemKind.Function);
                item.insertText = 'print()';
                item.range = document.getWordRangeAtPosition(position);
                item.detail = 'Python built-in function';
                item.documentation = new vscode.MarkdownString('Write values.');
                return [item];
            }
        }, '.')
    );
};
```

A provider may return an array, a `CompletionList`, null/undefined, or a Promise
of any of those. Multiple registrations and extension directories are combined.
The UI filters by a case-insensitive word prefix using `filterText` or `label`,
sorts by `sortText` or `label`, and displays at most 100 items. Each host also
caps its results at 100 before UI filtering. This is prefix matching, not VS
Code's fuzzy ranking. `CompletionList.isIncomplete` is accepted but not cached;
every text edit makes a fresh request.

## Supported surface

| API | Supported behavior |
| --- | --- |
| `languages.registerCompletionItemProvider(selector, provider, ...triggers)` | Returns disposable registration. Selectors: language string, `*`, arrays, or `{language, scheme}`. Patterns and other selector fields fail explicitly. |
| `CompletionItem(label, kind)` | String or `{label}` labels. Plain `insertText`, `range`, `detail`, `documentation`, `sortText`, `filterText`. Kind constants accepted, not rendered as icons. |
| `CompletionList(items, isIncomplete)` | Items consumed on each request. |
| `Position(line, character)` | Zero-based UTF-16 positions; comparison methods, `translate`, `with`. Python cursor indices are converted at the process boundary. |
| `Range(start, end)` / `Range(sl, sc, el, ec)` | `start`, `end`, `isEmpty`, `isSingleLine`, `contains`. Insertion range must be on one line and contain the cursor. |
| `MarkdownString` | `value`, `appendText`, `appendMarkdown`, `appendCodeblock`; shown as text. |
| `Uri.file(path)` | File URI with `scheme`, `authority`, `path`, `fsPath`, `query`, `fragment`, `toString`. |
| `TextDocument` | `uri`, `fileName`, `languageId`, `version`, `isDirty`, `isClosed`, `isUntitled`, `eol`, `lineCount`; `getText`, `lineAt`, `offsetAt`, `positionAt`, `validatePosition`, `validateRange`, `getWordRangeAtPosition`. |
| `ExtensionContext` | `subscriptions`, `extensionPath`, `extensionUri`, `asAbsolutePath`. |
| `workspace` | `workspaceFolders` (one folder), `rootPath`. No filesystem API or configuration emulation. |

`document` is a snapshot of the current **unsaved** editor buffer with normalized
LF newlines. `version` increases per request; it is not a document-change event
stream. `isDirty` is always true for these snapshots. The default word expression
recognizes Unicode letters/numbers, `_` and `$`; a custom RegExp is accepted.
Positions use UTF-16 code units, as JavaScript and VS Code do, not terminal cells.
Invalid ranges are rejected before any buffer change.

`CompletionTriggerKind` uses VS Code values: Invoked=0, TriggerCharacter=1,
TriggerForIncompleteCompletions=2. Currently the UI sends Invoked for both typing
and Ctrl+Space, so all language-matching providers are called; registered trigger
characters are accepted for source portability but do not limit UI invocation.
The internal protocol supports TriggerCharacter requests and filters registrations
for them. There is no incomplete-result cache.

The cancellation token has `isCancellationRequested=false` and
`onCancellationRequested` returns a no-op disposable. A newer request cancels the
old Python task; the extension process keeps running, a request still queued
behind a running one is answered with no items, and the stale answer is
dropped. Late results are ignored if the
buffer, cursor, focus or active tab changed. Providers should be side-effect-free.
A request, including activation, has a five-second timeout (fifteen for inline
completions); a timeout terminates the process. Hosts are terminated
when the editor exits. `deactivate` callbacks are not currently called.

## Inline completions (ghost text)

`languages.registerInlineCompletionItemProvider(selector, provider)` works like
VS Code's: `provideInlineCompletionItems(document, position, context, token)` may
return an array, an `InlineCompletionList` or null. The first item whose range
ends at the cursor and whose `insertText` starts with the text that range
replaces is drawn as dim ghost text after the cursor. Tab inserts it, Escape
dismisses it, typing the same characters shortens it, and any other edit or
cursor move removes it. Requests follow the same pause (250 ms) and `Ctrl+Space`
as the list. `context.triggerKind` is `InlineCompletionTriggerKind.Automatic`
(1) for the pause and `Invoke` (0) for `Ctrl+Space`.

Only the first line of the text is drawn and inserted; a multi-line suggestion
continues with the next request. `command` and `filterText` on an item, and
snippet text, report an unsupported error. The request protocol adds
`"inline": true`; the response items are `{insertText, range}`.

## Explicit limitations and errors

Snippets/tabstops (`SnippetString`), insert/replace dual ranges, `textEdit`,
`additionalTextEdits`, completion commands, `resolveCompletionItem`, commit
characters, preselect, VS Code event subscriptions, configuration, language
servers, diagnostics and inline ghost text from list providers are not implemented. Some presentation
fields are ignored; edit-affecting fields listed above are rejected. Unknown
members on the module and supported namespaces throw an unsupported API error.
Do not depend on feature detection through reading unknown members.

Extensions must use CommonJS `require('vscode')`; native ESM imports of `vscode`
are not intercepted. TypeScript must be compiled first. The compatibility layer
is not an implementation of every method on the classes listed above.

| Symptom | Action |
| --- | --- |
| No extension enabled | Start with `--completion-extension DIR`. |
| Node cannot be started | Install Node.js and ensure `node` is in PATH. |
| Cannot load package or main | Check directory, package.json, build output and dependencies. |
| Unsupported VS Code API | Adapt that call or isolate the completion provider in its own entry point. |
| No completions | Check document language, selector and prefix. Use Ctrl+Space. |
| Timeout / invalid response | Fix provider runtime errors, blocking work or output size. The next request starts a fresh host. |

Provider exceptions are shown as error notifications with the extension directory
name; the buffer is unchanged. Extension `console.log/info/debug` output is routed
away from the JSON channel; stderr is discarded by the Python host. Direct writes
to stdout are unsupported and can corrupt the protocol. Responses larger than
2 MiB fail rather than blocking the editor indefinitely.

## Internal process protocol

For maintainers: `node completion_host.cjs EXTENSION_DIR WORKSPACE_ROOT` reads
one JSON object per line and writes one response per line. A request contains
`id`, `path`, `languageId`, `text`, `version`,
`position: {line, character}`, `triggerKind`, `triggerCharacter` (nullable).
A response is `{id, items}` or `{id, items: [], error: "message"}`. Serialized
items use the plain fields in the table; ranges are `{start, end}` positions.
Requests are serialized per extension process. This transport is private;
the extension-facing interface is the `vscode` module above.
