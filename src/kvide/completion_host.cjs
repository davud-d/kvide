'use strict';

// A deliberately limited VS Code CommonJS completion compatibility host.
// This is not an extension sandbox: extensions execute with Node's privileges.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const readline = require('node:readline');
const { pathToFileURL } = require('node:url');
const util = require('node:util');

console.log = (...args) => process.stderr.write(util.format(...args) + '\n');
console.info = console.log;
console.debug = console.log;

function unsupported(name) {
    throw new Error(`Unsupported VS Code completion compatibility API: ${name}`);
}

function limited(object, name) {
    return new Proxy(object, {
        get(target, key, receiver) {
            if (typeof key === 'symbol' || Reflect.has(target, key)) {
                return Reflect.get(target, key, receiver);
            }
            return unsupported(`${name}.${key}`);
        },
    });
}

class Position {
    constructor(line, character) {
        if (!Number.isInteger(line) || line < 0 || !Number.isInteger(character) || character < 0) {
            throw new Error('Invalid Position: expected nonnegative integer line and character');
        }
        this.line = line;
        this.character = character;
    }
    isBefore(other) { return this.compareTo(other) < 0; }
    isBeforeOrEqual(other) { return this.compareTo(other) <= 0; }
    isAfter(other) { return this.compareTo(other) > 0; }
    isAfterOrEqual(other) { return this.compareTo(other) >= 0; }
    isEqual(other) { return this.compareTo(other) === 0; }
    compareTo(other) { return this.line - other.line || this.character - other.character; }
    translate(lineDelta = 0, characterDelta = 0) {
        if (typeof lineDelta === 'object') {
            return this.translate(lineDelta.lineDelta || 0, lineDelta.characterDelta || 0);
        }
        return new Position(this.line + lineDelta, this.character + characterDelta);
    }
    with(line = this.line, character = this.character) {
        if (typeof line === 'object') {
            return new Position(line.line ?? this.line, line.character ?? this.character);
        }
        return new Position(line, character);
    }
}

function position(value) { return new Position(value.line, value.character); }

class Range {
    constructor(start, end, endLine, endCharacter) {
        if (typeof start === 'number') {
            start = new Position(start, end);
            end = new Position(endLine, endCharacter);
        }
        start = position(start);
        end = position(end);
        [this.start, this.end] = start.isAfter(end) ? [end, start] : [start, end];
    }
    get isEmpty() { return this.start.isEqual(this.end); }
    get isSingleLine() { return this.start.line === this.end.line; }
    contains(value) {
        return value.start ? this.contains(value.start) && this.contains(value.end)
            : this.start.isBeforeOrEqual(value) && this.end.isAfterOrEqual(value);
    }
}

class CompletionItem {
    constructor(label, kind) { this.label = label; this.kind = kind; }
}
class CompletionList {
    constructor(items = [], isIncomplete = false) {
        this.items = items;
        this.isIncomplete = isIncomplete;
    }
}
class InlineCompletionItem {
    constructor(insertText, range) { this.insertText = insertText; this.range = range; }
}
class InlineCompletionList {
    constructor(items = []) { this.items = items; }
}
class MarkdownString {
    constructor(value = '', supportThemeIcons = false) {
        this.value = value;
        this.supportThemeIcons = supportThemeIcons;
    }
    appendText(value) {
        this.value += value.replace(/[\\`*_{}[\]()<>#+\-.!]/g, '\\$&');
        return this;
    }
    appendMarkdown(value) { this.value += value; return this; }
    appendCodeblock(value, language = '') {
        this.value += `\n\`\`\`${language}\n${value}\n\`\`\`\n`;
        return this;
    }
}
class Uri {
    static file(filePath) {
        const fsPath = path.resolve(filePath);
        const url = pathToFileURL(fsPath);
        return Object.freeze({
            scheme: 'file', authority: url.host, path: decodeURIComponent(url.pathname),
            fsPath, query: '', fragment: '', toString: () => url.href,
        });
    }
}

const CompletionItemKind = {};
['Text', 'Method', 'Function', 'Constructor', 'Field', 'Variable', 'Class',
 'Interface', 'Module', 'Property', 'Unit', 'Value', 'Enum', 'Keyword',
 'Snippet', 'Color', 'File', 'Reference', 'Folder', 'EnumMember', 'Constant',
 'Struct', 'Event', 'Operator', 'TypeParameter'].forEach((name, index) => {
    CompletionItemKind[name] = index;
    CompletionItemKind[index] = name;
});
const registrations = [];
const inlineRegistrations = [];
function selectorMatches(selector, document) {
    if (Array.isArray(selector)) return selector.some(value => selectorMatches(value, document));
    if (typeof selector === 'string') return selector === '*' || selector === document.languageId;
    return (selector.language === undefined || selector.language === '*' || selector.language === document.languageId)
        && (selector.scheme === undefined || selector.scheme === '*' || selector.scheme === document.uri.scheme);
}
function validateSelector(selector) {
    if (Array.isArray(selector)) {
        selector.forEach(validateSelector);
    } else if (typeof selector === 'string') {
        if (!selector) throw new Error('Unsupported empty document selector');
    } else if (selector && typeof selector === 'object') {
        for (const key of Object.keys(selector)) {
            if (!['language', 'scheme'].includes(key)) unsupported(`document selector.${key}`);
            if (typeof selector[key] !== 'string') throw new Error(`Invalid selector ${key}`);
        }
    } else {
        throw new Error('Unsupported document selector');
    }
}
const vscode = limited({
    Position, Range, CompletionItem, CompletionList, InlineCompletionItem, InlineCompletionList,
    InlineCompletionTriggerKind: Object.freeze({ Invoke: 0, Automatic: 1 }),
    CompletionItemKind: limited(CompletionItemKind, 'CompletionItemKind'),
    CompletionTriggerKind: Object.freeze({ Invoked: 0, TriggerCharacter: 1, TriggerForIncompleteCompletions: 2 }),
    MarkdownString, Uri,
    SnippetString: class SnippetString {
        constructor() { unsupported('SnippetString (snippets are not supported)'); }
    },
    languages: limited({
        registerCompletionItemProvider(selector, provider, ...triggers) {
            validateSelector(selector);
            if (!provider || typeof provider.provideCompletionItems !== 'function') {
                throw new Error('Completion provider must implement provideCompletionItems');
            }
            if (!triggers.every(value => typeof value === 'string')) throw new Error('Invalid trigger characters');
            const registration = { selector, provider, triggers };
            registrations.push(registration);
            return { dispose() {
                const index = registrations.indexOf(registration);
                if (index >= 0) registrations.splice(index, 1);
            } };
        },
        registerInlineCompletionItemProvider(selector, provider) {
            validateSelector(selector);
            if (!provider || typeof provider.provideInlineCompletionItems !== 'function') {
                throw new Error('Inline completion provider must implement provideInlineCompletionItems');
            }
            const registration = { selector, provider };
            inlineRegistrations.push(registration);
            return { dispose() {
                const index = inlineRegistrations.indexOf(registration);
                if (index >= 0) inlineRegistrations.splice(index, 1);
            } };
        },
    }, 'languages'),
}, 'vscode');
const originalLoad = Module._load;
Module._load = function(request, parent, isMain) {
    return request === 'vscode' ? vscode : originalLoad.call(this, request, parent, isMain);
};

function makeDocument(request) {
    if (typeof request.text !== 'string' || typeof request.path !== 'string'
        || typeof request.languageId !== 'string') throw new Error('Invalid completion document');
    const text = request.text;
    const lines = text.split(/\r\n|\r|\n/);
    const offsets = [0];
    const newline = /\r\n|\r|\n/g;
    let match;
    while ((match = newline.exec(text))) offsets.push(match.index + match[0].length);
    function validatePosition(value) {
        const p = position(value);
        const line = Math.min(p.line, lines.length - 1);
        return new Position(line, Math.min(p.character, lines[line].length));
    }
    function offsetAt(value) {
        const p = validatePosition(value);
        return offsets[p.line] + p.character;
    }
    function positionAt(value) {
        if (!Number.isFinite(value)) throw new Error('Invalid document offset');
        const offset = Math.max(0, Math.min(Math.floor(value), text.length));
        let low = 0, high = offsets.length;
        while (low + 1 < high) {
            const mid = (low + high) >>> 1;
            if (offsets[mid] <= offset) low = mid;
            else high = mid;
        }
        return new Position(low, Math.min(offset - offsets[low], lines[low].length));
    }
    function lineAt(value) {
        const line = typeof value === 'number' ? value : value.line;
        if (!Number.isInteger(line) || line < 0 || line >= lines.length) throw new Error('Invalid document line');
        const content = lines[line];
        const firstNonWhitespaceCharacterIndex = content.search(/\S/);
        return {
            lineNumber: line, text: content,
            range: new Range(line, 0, line, content.length),
            rangeIncludingLineBreak: line + 1 < lines.length
                ? new Range(line, 0, line + 1, 0) : new Range(line, 0, line, content.length),
            firstNonWhitespaceCharacterIndex: firstNonWhitespaceCharacterIndex < 0
                ? content.length : firstNonWhitespaceCharacterIndex,
            isEmptyOrWhitespace: firstNonWhitespaceCharacterIndex < 0,
        };
    }
    return limited({
        uri: Uri.file(request.path), fileName: path.resolve(request.path),
        languageId: request.languageId, version: request.version ?? 1, isUntitled: false,
        isDirty: true, isClosed: false, lineCount: lines.length,
        eol: text.includes('\r\n') ? 2 : 1,
        getText(range) { return range ? text.slice(offsetAt(range.start), offsetAt(range.end)) : text; },
        lineAt, offsetAt, positionAt, validatePosition,
        validateRange(range) { return new Range(validatePosition(range.start), validatePosition(range.end)); },
        getWordRangeAtPosition(value, regex = /[\p{L}\p{N}_$]+/u) {
            const p = validatePosition(value);
            const expression = new RegExp(regex.source, regex.flags.replace(/[gy]/g, '') + 'g');
            let word;
            while ((word = expression.exec(lines[p.line]))) {
                if (!word[0].length) throw new Error('Word expression must not match empty text');
                if (word.index <= p.character && word.index + word[0].length >= p.character) {
                    return new Range(p.line, word.index, p.line, word.index + word[0].length);
                }
            }
            return undefined;
        },
    }, 'TextDocument');
}

function serializeRange(value) {
    if (!value || !value.start || !value.end) unsupported('completion insert/replace range');
    return { start: position(value.start), end: position(value.end) };
}
function serializeItem(item, document, cursor) {
    if (!item || typeof item !== 'object') throw new Error('Invalid completion item');
    const label = typeof item.label === 'string' ? item.label : item.label?.label;
    if (typeof label !== 'string') throw new Error('Completion item label must be a string');
    if (item.textEdit !== undefined || item.additionalTextEdits !== undefined || item.command !== undefined) {
        unsupported('completion textEdit/additionalTextEdits/command');
    }
    const insertText = item.insertText ?? label;
    if (typeof insertText !== 'string' || item.insertTextFormat === 2) {
        unsupported('snippet insertText (only plain text is supported)');
    }
    const result = {
        label, insertText,
        range: serializeRange(item.range ?? document.getWordRangeAtPosition(cursor) ?? new Range(cursor, cursor)),
    };
    for (const key of ['detail', 'sortText', 'filterText']) {
        if (item[key] !== undefined) {
            if (typeof item[key] !== 'string') throw new Error(`Completion ${key} must be a string`);
            result[key] = item[key];
        }
    }
    if (item.documentation !== undefined) {
        const documentation = typeof item.documentation === 'string' ? item.documentation : item.documentation.value;
        if (typeof documentation !== 'string') throw new Error('Invalid completion documentation');
        result.documentation = documentation;
    }
    return result;
}

function serializeInlineItem(item, document, cursor) {
    if (!item || typeof item !== 'object') throw new Error('Invalid inline completion item');
    if (item.command !== undefined || item.filterText !== undefined) {
        unsupported('inline completion command/filterText');
    }
    if (typeof item.insertText !== 'string') {
        unsupported('inline completion insertText (only plain text is supported)');
    }
    return { insertText: item.insertText, range: serializeRange(item.range ?? new Range(cursor, cursor)) };
}

const extensionDir = path.resolve(process.argv[2] || '.');
const workspaceRoot = path.resolve(process.argv[3] || '.');
let activation;
function activateOnce() {
    if (!activation) activation = Promise.resolve().then(async () => {
        const manifest = JSON.parse(fs.readFileSync(path.join(extensionDir, 'package.json'), 'utf8'));
        if (typeof manifest.main !== 'string') throw new Error('CommonJS extension package.json must declare main');
        vscode.workspace = limited({
            workspaceFolders: [{ uri: Uri.file(workspaceRoot), name: path.basename(workspaceRoot), index: 0 }],
            rootPath: workspaceRoot,
        }, 'workspace');
        const extension = require(path.resolve(extensionDir, manifest.main));
        if (typeof extension.activate !== 'function') throw new Error('Extension must export activate(context)');
        const context = limited({
            subscriptions: [], extensionPath: extensionDir, extensionUri: Uri.file(extensionDir),
            asAbsolutePath: relative => path.resolve(extensionDir, relative),
        }, 'ExtensionContext');
        await extension.activate(context);
    });
    return activation;
}
const token = Object.freeze({
    isCancellationRequested: false,
    onCancellationRequested() { return { dispose() {} }; },
});
async function complete(request) {
    await activateOnce();
    const document = makeDocument(request);
    const cursor = position(request.position);
    if (!document.validatePosition(cursor).isEqual(cursor)) throw new Error('Completion position is outside document');
    const triggerKind = request.triggerKind ?? 0;
    if (![0, 1, 2].includes(triggerKind)) throw new Error('Invalid completion triggerKind (expected VS Code 0, 1 or 2)');
    if (triggerKind === 1 && typeof request.triggerCharacter !== 'string') throw new Error('Missing triggerCharacter');
    const context = { triggerKind, triggerCharacter: request.triggerCharacter };
    const items = [];
    for (const { selector, provider, triggers } of registrations.slice()) {
        if (!selectorMatches(selector, document)) continue;
        if (triggerKind === 1 && !triggers.includes(request.triggerCharacter)) continue;
        const supplied = await provider.provideCompletionItems(document, cursor, token, context);
        if (supplied == null) continue;
        const results = Array.isArray(supplied) ? supplied : supplied.items;
        if (!Array.isArray(results)) throw new Error('Provider must return completion items or CompletionList');
        for (const item of results) {
            items.push(serializeItem(item, document, cursor));
            if (items.length === 100) return items;
        }
    }
    return items;
}

async function completeInline(request) {
    await activateOnce();
    const document = makeDocument(request);
    const cursor = position(request.position);
    if (!document.validatePosition(cursor).isEqual(cursor)) throw new Error('Completion position is outside document');
    const context = { triggerKind: request.triggerKind ?? 0, selectedCompletionInfo: undefined };
    if (![0, 1].includes(context.triggerKind)) throw new Error('Invalid inline triggerKind (expected 0 or 1)');
    const items = [];
    for (const { selector, provider } of inlineRegistrations.slice()) {
        if (!selectorMatches(selector, document)) continue;
        const supplied = await provider.provideInlineCompletionItems(document, cursor, context, token);
        if (supplied == null) continue;
        const results = Array.isArray(supplied) ? supplied : supplied.items;
        if (!Array.isArray(results)) throw new Error('Provider must return inline completion items or InlineCompletionList');
        for (const item of results) {
            items.push(serializeInlineItem(item, document, cursor));
            if (items.length === 100) return items;
        }
    }
    return items;
}

// Requests run one at a time. An inline request that is still waiting when a newer one arrives
// is answered with no items: the editor has moved on and its answer would be discarded.
const queue = [];
let busy = false;
function respond(response) { process.stdout.write(JSON.stringify(response) + '\n'); }
function parsed(line) {
    try { return JSON.parse(line); } catch (error) { return null; }
}
async function handle(line) {
    let request;
    try {
        request = JSON.parse(line);
        if (!request || typeof request !== 'object' || Array.isArray(request)) throw new Error('Invalid request object');
        return { id: request.id ?? null, items: await (request.inline ? completeInline(request) : complete(request)) };
    } catch (error) {
        return { id: request?.id ?? null, items: [], error: error instanceof Error ? error.message : String(error) };
    }
}
async function pump() {
    if (busy) return;
    busy = true;
    while (queue.length) {
        const line = queue.shift();
        const request = parsed(line);
        if (queue.length && request?.inline) respond({ id: request.id ?? null, items: [] });
        else respond(await handle(line));
    }
    busy = false;
}
readline.createInterface({ input: process.stdin, crlfDelay: Infinity }).on('line', line => {
    queue.push(line);
    pump().catch(error => { console.error(error); process.exitCode = 1; });
});
