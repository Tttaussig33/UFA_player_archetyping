const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { makeReport } = require('./extension/portable.cjs');
const sourceDirectory = process.argv[2];
if (!sourceDirectory) throw new Error('Provide the directory containing the source reports.');
const output = path.resolve(__dirname, '../previews');
fs.mkdirSync(path.join(output, 'html'), {recursive:true});
const names = ['UFA-dead-disc-first-pass', 'UFA-pull-centering', 'UFA-oline-regain-hucking', 'UFA-possession-review'];
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const receipt = names.map(name => {
  const sourcePath = path.resolve(sourceDirectory, name + '.canvas.tsx');
  const source = fs.readFileSync(sourcePath, 'utf8');
  const target = path.join(output, name + '.canvas.tsx');
  const htmlPath = path.join(output, 'html', name + '.ufa.html');
  const html = makeReport(source, sourcePath);
  fs.writeFileSync(target, source);
  fs.writeFileSync(htmlPath, html);
  return {sourcePath, sourceSha256:sha(source), reportPath:target,
    reportSha256:sha(fs.readFileSync(target)), htmlPath, htmlSha256:sha(html)};
});
fs.writeFileSync(path.join(output, 'export-receipt.json'), JSON.stringify({
  exportedAt:new Date().toISOString(), note:'Presentation conversion only. The TSX source and embedded research data are copied without changes.', reports:receipt
}, null, 2) + '\n');
console.log(JSON.stringify(receipt.map(r => ({report:r.reportPath, html:r.htmlPath, unchanged:r.sourceSha256 === r.reportSha256})), null, 2));
