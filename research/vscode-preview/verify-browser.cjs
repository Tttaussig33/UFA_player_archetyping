const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {chromium} = require('/Users/teddytaussig/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const preview = path.resolve(__dirname, '../previews');
const output = path.join(__dirname, 'verification');
const names = ['UFA-dead-disc-first-pass', 'UFA-pull-centering', 'UFA-oline-regain-hucking', 'UFA-possession-review'];
function dataFor(name) {
  const source = fs.readFileSync(path.join(preview, name + '.canvas.tsx'), 'utf8');
  const line = source.split('\n').find(line => /^const DATA\b/.test(line));
  return JSON.parse(line.slice(line.indexOf('=') + 1).trim().replace(/;$/, ''));
}
async function inspect(page) {
  return page.evaluate(() => ({
    title:document.querySelector('h1').textContent,
    rows:Array.from(document.querySelectorAll('tbody')).map(body => Array.from(body.rows).map(row => Array.from(row.cells).map(c => c.textContent))),
    bars:Array.from(document.querySelectorAll('rect[data-value]')).map(r => ({value:Number(r.dataset.value), category:r.dataset.category, series:r.dataset.series})),
    charts:document.querySelectorAll('svg').length,
    overflow:document.documentElement.scrollWidth > innerWidth + 1,
    text:document.body.innerText
  }));
}
async function verify(page, name, choice) {
  const data = dataFor(name), actual = await inspect(page);
  assert.equal(actual.overflow, false, 'Page must not overflow horizontally');
  if (name.includes('dead-disc')) {
    const c = data[choice];
    const union = [...new Map([...c.aec_leaders, ...c.assist_leaders].map(p => [p.name, p])).values()]
      .sort((a, b) => b.thrower_aec - a.thrower_aec || a.name.localeCompare(b.name));
    assert.deepEqual(actual.rows[0], union.map(p => [p.name, String(p.restart_events_including_stalls), String(p.assists), p.thrower_aec.toFixed(3), p.huck_completions + ' / ' + p.huck_attempts]));
    assert.deepEqual(actual.rows[1], c.huck_counts.map(p => [p.name, ...[p.huck_attempts, p.huck_completions, p.huck_drops, p.huck_assists].map(String)]));
    assert.deepEqual(actual.bars.map(b => b.value), [...c.assist_leaders.map(p => p.assists), ...c.aec_leaders.map(p => Number(p.thrower_aec.toFixed(3)))]);
    assert(actual.text.includes(c.summary.restart_events_including_stalls.toLocaleString() + ' attributed restart events'));
  } else if (name.includes('pull-centering')) {
    assert.equal(actual.rows[0].length, 22);
    assert.deepEqual(actual.rows[0], data.teams[choice].map(t => [
      t.team + (t.games === 11 ? ' *' : ''),
      t.leaders.map(p => p.name).join(' / ') + (t.leaders.length > 1 ? ' (tie)' : ''),
      t.leader_count + ' / ' + t.qualifying_centering_passes + (t.leaders.length > 1 ? ' each' : ''),
      (100 * t.leader_share).toFixed(1) + '%' + (t.leaders.length > 1 ? ' each' : '')
    ]));
    const sorted = [...data.teams[choice]].sort((a,b) => b.leader_share - a.leader_share || a.team.localeCompare(b.team));
    assert.deepEqual(actual.bars.map(b => b.value), sorted.map(t => Number((100 * t.leader_share).toFixed(1))));
    assert(actual.text.includes(data.counts[choice].toLocaleString() + ' qualifying receptions'));
  } else if (name.includes('oline-regain')) {
    const pct = x => (100*x).toFixed(2)+'%';
    const signed = x => (x>0?'+':'')+x.toFixed(2);
    const sorted = [...data.teams].sort((a,b) => a.team_name.localeCompare(b.team_name));
    assert.deepEqual(actual.rows[0], sorted.map(t => [t.team_name, t.opening.hucks+' / '+t.opening.n.toLocaleString(), pct(t.opening.rate), t.regained.hucks+' / '+t.regained.n.toLocaleString(), pct(t.regained.rate), signed(t.difference_pp)]));
    assert.deepEqual(actual.bars.map(b => b.value), data.stages.flatMap(s => [Number((100*s.opening.rate).toFixed(2)), Number((100*s.regained.rate).toFixed(2))]));
    assert.equal(await page.locator('circle').count(), 22);
    assert.equal(actual.charts, 2);
    assert(actual.text.includes('4.96%') && actual.text.includes('5.49%'));
  } else {
    const c = data.cases.find(c => c.id === choice);
    assert.deepEqual(actual.rows[0], c.throws.map(t => [String(t.n), t.from+' → '+t.to, t.outcome+(t.huck?' · Huck':'')]));
    assert.equal(actual.charts, 1);
    assert.equal(await page.locator('[data-throw-number]').count(), c.throws.length);
    for (const focus of ['all', String(c.throws.at(-1).n), '1']) {
      await page.locator('select').nth(1).selectOption(focus);
      const line = page.locator('[data-throw-number="'+(focus==='all'?1:focus)+'"] line');
      const t = c.throws[focus==='all'?0:Number(focus)-1];
      for (const [attr, expected] of Object.entries({x1:60+(t.xy[0]+26.6667)*5,y1:650-t.xy[1]*5,x2:60+(t.xy[2]+26.6667)*5,y2:650-t.xy[3]*5})) {
        assert(Math.abs(Number(await line.getAttribute(attr))-expected)<0.00001, 'Field geometry must match source coordinates');
      }
    }
  }
  return {name, choice, title:actual.title, rows:actual.rows.map(r => r.length), charts:actual.charts, barValuesVerified:actual.bars.length};
}
(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const results = [], errors = [], externalRequests = [];
  try {
    for (const name of names) {
      const page = await browser.newPage({viewport:{width:1200,height:900}, colorScheme:'light'});
      page.on('pageerror', e => errors.push(String(e)));
      page.on('request', r => { if (/^https?:/.test(r.url())) externalRequests.push(r.url()); });
      await page.goto(pathToFileURL(path.join(preview, 'html', name + '.ufa.html')).href);
      await page.waitForSelector('svg');
      const firstSelect = page.locator('select').first();
      const options = await page.locator('select').count() ? await firstSelect.locator('option').evaluateAll(nodes => nodes.map(n => n.value)) : [];
      for (const choice of options.length ? options : [null]) {
        if (choice) await firstSelect.selectOption(choice);
        results.push(await verify(page, name, choice));
      }
      if (options.length) await firstSelect.selectOption(options[0]);
      const summary = page.locator('summary');
      if (await summary.count()) {
        await summary.click();
        assert.equal(await page.locator('details').getAttribute('open'), '');
        assert(await page.getByText('UFA', {exact:false}).count() > 0);
      }
      await page.screenshot({path:path.join(output, name + '-wide.png'), fullPage:true});
      await page.setViewportSize({width:420,height:800});
      await page.emulateMedia({colorScheme:'dark'});
      await page.waitForTimeout(150);
      await verify(page, name, options[0] || null);
      await page.screenshot({path:path.join(output, name + '-narrow-dark.png'), fullPage:true});
      await page.close();
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(externalRequests, []);
    const report = {checkedAt:new Date().toISOString(), passed:true, results, javascriptErrors:errors, externalRequests, checkedViewports:['1200px light','420px dark']};
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
