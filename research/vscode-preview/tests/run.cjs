const vscode = require('vscode');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const names = ['UFA-dead-disc-first-pass', 'UFA-pull-centering', 'UFA-oline-regain-hucking', 'UFA-possession-review'];
const expected = [[6, 7], [22], [3, 3, 3, 3, 5, 22, 3, 3, 4, 7], [5]];
const expectedCharts = [2, 1, 6, 1];
const directory = path.resolve(__dirname, '../../previews');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(read, label) {
  const start = Date.now();
  while (Date.now() - start < 25000) {
    const value = read();
    if (value) return value;
    await delay(150);
  }
  throw new Error('Timed out: ' + label);
}
exports.run = async function () {
  const results = [];
  for (let index = 0; index < names.length; index++) {
    for (const kind of ['tsx', 'html']) {
      const name = names[index];
      const uri = vscode.Uri.file(kind === 'tsx'
        ? path.join(directory, name + '.canvas.tsx')
        : path.join(directory, 'html', name + '.ufa.html'));
      // Use ordinary file opening to verify the default editor association.
      await vscode.commands.executeCommand('vscode.open', uri, {preview:false});
      await waitFor(() => vscode.window.tabGroups.activeTabGroup.activeTab?.input?.viewType === 'ufa.researchPreview', 'default rendered editor for ' + name);
      const extension = vscode.extensions.getExtension('local-ufa.research-preview');
      const api = await extension.activate();
      const result = await waitFor(() => api.previewDiagnostics()[uri.toString()], 'rendered report ' + name);
      assert.equal(result.error, undefined);
      assert.deepEqual(result.tableRows, expected[index]);
      assert.equal(result.chartCount, expectedCharts[index]);
      results.push({name, kind, editor:'ufa.researchPreview', ...result});
      await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
    }
  }
  fs.mkdirSync(path.resolve(__dirname, '../verification'), {recursive:true});
  fs.writeFileSync(path.resolve(__dirname, '../verification/vscode-results.json'), JSON.stringify({
    checkedAt:new Date().toISOString(), vscodeVersion:vscode.version, passed:true, results
  }, null, 2));
  console.log('Verified automatic rendering in VS Code for all 4 TSX files and all 4 HTML exports.');
};
