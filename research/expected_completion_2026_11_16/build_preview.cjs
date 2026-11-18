/* Build the existing canvas and portable preview without changing the runtime. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {makeReport} = require('../vscode-preview/extension/portable.cjs');
const repo = path.resolve(__dirname, '../..');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'results.json'), 'utf8'));
const inference = JSON.parse(fs.readFileSync(path.join(__dirname, 'team_significance.json'), 'utf8'));
for (const [file, digest] of Object.entries(inference.inputs)) {
  const actual = crypto.createHash('sha256').update(fs.readFileSync(path.join(repo, file))).digest('hex');
  if (actual !== digest) throw new Error('Recalculate significance after source change: ' + file);
}
for (const [scope, values] of Object.entries(data.scopes)) {
  const checked = inference.scopes[scope];
  values.league.inference = checked.league;
  for (const row of values.teams) {
    const record = checked.teams[row.team];
    if (!record || Math.abs(record.difference_pp-row.change_pp) > 1e-9) throw new Error('Inference mismatch: ' + row.team);
    row.inference = record;
  }
  values.significanceSummary = {nominal_teams:checked.nominal_teams,corrected_teams:checked.corrected_teams};
}
data.displayInference = {method:inference.method,draws:inference.draws,definition:inference.definition,multiplicity:inference.multiplicity};
data.buildStatus = 'complete';
const template = fs.readFileSync(path.join(__dirname, 'canvas-template.tsx'), 'utf8');
if (template.split('__REVIEWED_DATA__').length !== 2) throw new Error('Expected one reviewed-data placeholder.');
const source = template.replace('__REVIEWED_DATA__', JSON.stringify(data));
const name = 'UFA-expected-completion-by-possession.canvas.tsx';
const managed = '/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases/' + name;
const copy = path.join(repo, 'research/previews', name);
const html = path.join(repo, 'research/previews/html/UFA-expected-completion-by-possession.ufa.html');
const compiled = makeReport(source, name);
fs.writeFileSync(managed, source);
fs.writeFileSync(copy, source);
fs.writeFileSync(html, compiled);
console.log('Built both starting-location filters with source-verified significance markers.');
