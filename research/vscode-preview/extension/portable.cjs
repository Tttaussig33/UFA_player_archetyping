const fs = require('node:fs');
const path = require('node:path');
const ts = require('./vendor/typescript.js');
const supported = new Set(['BarChart','Grid','H1','H2','Select','Stack','Table','Text','useHostTheme','useState']);

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function makeReport(source, filename) {
  const match = source.match(/import\s*\{([^}]+)\}\s*from\s*["']cursor\/canvas["'];?/);
  if (!match) throw new Error('The report must use the supported UFA display components.');
  const names = match[1].split(',').map(s => s.trim()).filter(Boolean);
  const unknown = names.filter(name => !supported.has(name));
  if (unknown.length) throw new Error('Unsupported report components: ' + unknown.join(', '));
  let body = source.replace(match[0], '');
  if (/\bimport\s/.test(body)) throw new Error('Additional imports are not supported by this offline report preview.');
  const component = body.match(/export\s+default\s+function\s+(\w+)/);
  if (!component) throw new Error('A named default report function is required.');
  body = body.replace(component[0], 'function ' + component[1]);
  const compiled = ts.transpileModule(body, {
    fileName: path.basename(filename), reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ES2020, moduleDetection: ts.ModuleDetectionKind.Legacy,
      jsx: ts.JsxEmit.React, jsxFactory: 'h', jsxFragmentFactory: 'Fragment', removeComments: true }
  });
  const errors = (compiled.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
  if (errors.length) throw new Error(errors.map(d => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('\n'));
  const runtime = fs.readFileSync(path.join(__dirname, 'report-runtime.js'), 'utf8');
  const css = fs.readFileSync(path.join(__dirname, 'report.css'), 'utf8');
  const script = `(() => { const { h, ${names.join(', ')} } = window.UFAPreview;\n${compiled.outputText}\nwindow.UFAPreview.render(${component[1]}); })();`;
  const title = path.basename(filename).replace(/\.canvas\.tsx$/, '').replaceAll('-', ' ');
  return `<!doctype html>\n<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title><style>${css}</style></head><body><main id="ufa-report"></main><script>${runtime.replace(/<\/script/gi, '<\\/script')}</script><script>${script.replace(/<\/script/gi, '<\\/script')}</script></body></html>\n`;
}

module.exports = { makeReport };
