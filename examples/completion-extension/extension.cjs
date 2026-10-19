'use strict';
const vscode = require('vscode');

exports.activate = function activate(context) {
    context.subscriptions.push(vscode.languages.registerCompletionItemProvider('python', {
        provideCompletionItems(document, position, token, completionContext) {
            if (token.isCancellationRequested) return [];
            const item = new vscode.CompletionItem('print', vscode.CompletionItemKind.Function);
            item.insertText = 'print()';
            item.detail = 'Python built-in function';
            item.documentation = new vscode.MarkdownString('Write values to standard output.');
            item.range = document.getWordRangeAtPosition(position);
            return new vscode.CompletionList([item], false);
        },
    }));
};
