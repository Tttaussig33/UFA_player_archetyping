const vscode = require('vscode');
const crypto = require('node:crypto');
const { makeReport } = require('./portable.cjs');

function securedHtml(html, nonce) {
  const policy = `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none';`;
  return html
    .replace(/<head>/i, `<head><meta http-equiv="Content-Security-Policy" content="${policy}">`)
    .replace(/<script\b([^>]*)>/gi, (_, attrs) => `<script${attrs.replace(/\snonce\s*=\s*["'][^"']*["']/gi, '')} nonce="${nonce}">`);
}

function activate(context) {
  const status = new Map();
  const provider = {
    resolveCustomTextEditor(document, panel) {
      const uri = document.uri.toString();
      panel.webview.options = { enableScripts: true, localResourceRoots: [] };
      let timer;
      function refresh() {
        try {
          const html = document.uri.path.endsWith('.tsx')
            ? makeReport(document.getText(), document.uri.path)
            : document.getText();
          if (!/^<!doctype html>/i.test(html.trim())) throw new Error('This file is not a self-contained UFA report.');
          panel.webview.html = securedHtml(html, crypto.randomBytes(20).toString('hex'));
        } catch (error) {
          const message = String(error.message).replace(/[&<>]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[c]));
          panel.webview.html = `<html><body><h2>Report preview needs attention</h2><p>${message}</p><p>Use Reopen Editor With → Text Editor to inspect the source.</p></body></html>`;
          status.set(uri, { error: String(error.message) });
        }
      }
      const changed = vscode.workspace.onDidChangeTextDocument(event => {
        if (event.document.uri.toString() === uri) {
          clearTimeout(timer);
          timer = setTimeout(refresh, 100);
        }
      });
      const messages = panel.webview.onDidReceiveMessage(message => {
        // Rendering diagnostics only; report scripts cannot invoke host actions.
        if (message?.type === 'ufa-preview-ready') {
          status.set(uri, {
            title: String(message.title).slice(0, 200),
            tableRows: Array.isArray(message.tableRows) ? message.tableRows.map(Number) : [],
            chartCount: Number(message.chartCount),
            selectors: Array.isArray(message.selectors) ? message.selectors.map(String) : [],
          });
        }
      });
      panel.onDidDispose(() => {
        clearTimeout(timer);
        changed.dispose();
        messages.dispose();
        status.delete(uri);
      });
      refresh();
    }
  };
  context.subscriptions.push(vscode.window.registerCustomEditorProvider('ufa.researchPreview', provider, {
    webviewOptions: { retainContextWhenHidden: true }, supportsMultipleEditorsPerDocument: true
  }));
  return { previewDiagnostics: () => Object.fromEntries(status) };
}

module.exports = { activate, securedHtml };
