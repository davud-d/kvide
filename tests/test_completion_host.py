"""Subprocess tests for the limited Node CommonJS completion compatibility host."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


NODE = shutil.which("node")
HOST = Path(__file__).resolve().parents[1] / "src" / "kvide" / "completion_host.cjs"
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")


def _request(**changes: object) -> dict:
    return {
        "id": 1,
        "path": "example.js",
        "languageId": "javascript",
        "text": "hello",
        "position": {"line": 0, "character": 3},
        "triggerKind": 0,
        **changes,
    }


def _run(tmp_path: Path, source: str, requests: list[dict]) -> tuple[list[dict], str]:
    extension = tmp_path / "extension"
    extension.mkdir(exist_ok=True)
    (extension / "package.json").write_text(json.dumps({"main": "main.cjs"}), encoding="utf-8")
    (extension / "main.cjs").write_text(source, encoding="utf-8")
    process = subprocess.run(
        [NODE, str(HOST), str(extension), str(tmp_path)],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return [json.loads(line) for line in process.stdout.splitlines()], process.stderr


def test_async_provider_protocol_and_activation_once(tmp_path: Path) -> None:
    responses, stderr = _run(tmp_path, """
const v = require('vscode');
let activated = 0;
exports.activate = async context => {
    await new Promise(resolve => setTimeout(resolve, 5));
    activated++;
    console.log('extension activated');
    context.subscriptions.push(v.languages.registerCompletionItemProvider('javascript', {
        async provideCompletionItems(document, position, token, trigger) {
            await new Promise(resolve => setTimeout(resolve, 5));
            if (token.isCancellationRequested) throw Error('cancelled');
            token.onCancellationRequested(() => {}).dispose();
            const item = new v.CompletionItem('greeting', v.CompletionItemKind.Function);
            item.insertText = 'hello()';
            item.detail = `${activated}:${v.CompletionItemKind.Text}:${trigger.triggerKind}`;
            item.documentation = new v.MarkdownString('**docs**').appendText('!');
            item.sortText = '001';
            item.filterText = 'hello';
            item.range = new v.Range(new v.Position(0, 0), position);
            return new v.CompletionList([item]);
        }
    }));
};
""", [_request(), _request(id=2)])
    assert [response["id"] for response in responses] == [1, 2]
    assert all("error" not in response for response in responses)
    item = responses[0]["items"][0]
    assert item == {
        "label": "greeting", "insertText": "hello()", "detail": "1:0:0",
        "documentation": "**docs**\\!", "sortText": "001", "filterText": "hello",
        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 3}},
    }
    assert responses[1]["items"] == responses[0]["items"]
    assert stderr.count("extension activated") == 1


def test_selectors_triggers_and_disposal(tmp_path: Path) -> None:
    responses, _ = _run(tmp_path, """
const v = require('vscode');
exports.activate = () => {
    const add = (selector, label, ...triggers) => v.languages.registerCompletionItemProvider(
        selector, { provideCompletionItems: () => [{label}] }, ...triggers);
    add(['python', {language: 'javascript', scheme: 'file'}], 'matched', '.');
    add({language: 'javascript', scheme: 'untitled'}, 'wrong-scheme', '.');
    add('python', 'wrong-language', '.');
    add('*', 'wildcard', ':');
    add('javascript', 'disposed').dispose();
};
""", [
        _request(),
        _request(id=2, triggerKind=1, triggerCharacter="."),
        _request(id=3, triggerKind=1, triggerCharacter=":"),
        _request(id=4, triggerKind=1, triggerCharacter="!"),
        _request(id=5, languageId="python"),
    ])
    assert [[item["label"] for item in response["items"]] for response in responses] == [
        ["matched", "wildcard"], ["matched"], ["wildcard"], [],
        ["matched", "wrong-language", "wildcard"],
    ]


def test_document_utf16_crlf_and_word_range(tmp_path: Path) -> None:
    responses, _ = _run(tmp_path, """
const v = require('vscode');
exports.activate = () => v.languages.registerCompletionItemProvider('javascript', {
    provideCompletionItems(d, p) {
        const word = d.getWordRangeAtPosition(p);
        const line = d.lineAt(1);
        const details = {
            text: d.getText(), word: d.getText(word), offset: d.offsetAt(p),
            roundtrip: d.positionAt(d.offsetAt(p)), line: line.text,
            newline: d.positionAt(7), lines: d.lineCount, eol: d.eol,
            end: d.positionAt(1000), clamped: d.offsetAt(new v.Position(100, 100)),
            indentation: line.firstNonWhitespaceCharacterIndex,
            file: d.uri.scheme, fileName: d.fileName, uri: v.Uri.file(d.fileName).toString()
        };
        return [{label: {label: 'unicode'}, detail: JSON.stringify(details)}];
    }
});
""", [_request(text="😀abc\r\n  café\n", position={"line": 1, "character": 5})])
    assert "error" not in responses[0]
    item = responses[0]["items"][0]
    details = json.loads(item["detail"])
    assert details["text"] == "😀abc\r\n  café\n"
    assert details["word"] == "café"
    assert details["offset"] == 12
    assert details["roundtrip"] == {"line": 1, "character": 5}
    assert details["newline"] == {"line": 1, "character": 0}
    assert details["end"] == {"line": 2, "character": 0}
    assert details["clamped"] == 14
    assert details["line"] == "  café"
    assert details["lines"] == 3
    assert details["eol"] == 2
    assert details["indentation"] == 2
    assert details["file"] == "file"
    assert details["uri"].startswith("file://")
    assert item["range"] == {"start": {"line": 1, "character": 2}, "end": {"line": 1, "character": 6}}


@pytest.mark.parametrize(("source", "error"), [
    ("exports.activate = () => { throw Error('activation failed'); };", "activation failed"),
    ("require('vscode').window.createOutputChannel('test');", "vscode.window"),
    ("exports.activate = () => require('vscode').workspace.getConfiguration();", "workspace.getConfiguration"),
    ("exports.activate = () => require('vscode').languages.registerCompletionItemProvider({language:'javascript', pattern:'**/*.js'}, {});", "selector.pattern"),
    ("exports.activate = () => require('vscode').languages.registerCompletionItemProvider(null, {});", "selector"),
    ("exports.activate = () => require('vscode').languages.registerCompletionItemProvider('javascript', {provideCompletionItems: async () => {throw Error('provider failed');}});", "provider failed"),
    ("exports.activate = () => require('vscode').languages.registerCompletionItemProvider('javascript', {provideCompletionItems: () => [{label:'bad', insertText:{value:'${1:x}'}}]});", "snippet insertText"),
    ("exports.activate = () => { new (require('vscode').SnippetString)('x'); };", "snippets are not supported"),
    ("exports.activate = () => require('vscode').languages.registerCompletionItemProvider('javascript', {provideCompletionItems: () => ({wrong: []})});", "Provider must return"),
])
def test_explicit_errors(tmp_path: Path, source: str, error: str) -> None:
    responses, _ = _run(tmp_path, source, [_request(), _request(id=2)])
    assert len(responses) == 2
    assert all(response["items"] == [] and error in response["error"] for response in responses)


def test_provider_errors_do_not_kill_persistent_host(tmp_path: Path) -> None:
    responses, _ = _run(tmp_path, """
const v = require('vscode');
exports.activate = () => v.languages.registerCompletionItemProvider('javascript', {
    provideCompletionItems(document) {
        if (document.getText() === 'bad') throw Error('bad document');
        return [{label: 'good'}];
    }
});
""", [_request(text="bad"), _request(id=2)])
    assert responses[0]["error"] == "bad document"
    assert responses[1]["items"][0]["label"] == "good"
    assert "error" not in responses[1]


def test_limit_and_default_insertion_range(tmp_path: Path) -> None:
    responses, _ = _run(tmp_path, """
const v = require('vscode');
exports.activate = () => v.languages.registerCompletionItemProvider('javascript', {
    provideCompletionItems: () => Array.from({length: 150}, (_, i) => ({label: `item${i}`}))
});
""", [_request()])
    items = responses[0]["items"]
    assert len(items) == 100
    assert items[-1]["label"] == "item99"
    assert items[0]["insertText"] == "item0"
    assert items[0]["range"] == {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}}
