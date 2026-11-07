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
    const pct = x => (100*x).toFixed(1)+'%';
    const signed = x => (x>0?'+':'')+x.toFixed(1);
    const range = (v,s) => v.map(x=>(s*x).toFixed(1)).join(' to ');
    const [scoreView, pool, metric, teamId] = await page.locator('select').evaluateAll(ss => ss.map(s => s.value));
    const sorted = data.teams.filter(t=>pool==='all'||data.follow_up.playoff_team_ids.includes(t.team)).sort((a,b) => a.team_name.localeCompare(b.team_name));
    const count = metric.startsWith('throws'), scale = count?1:100;
    const groupText = g => !g.n || g.estimate==null?'— (0)':(count?g.estimate.toFixed(1):pct(g.estimate))+' ('+g.n.toLocaleString()+')';
    assert.deepEqual(actual.rows[5], sorted.map(t => {
      const c=data.team_changes[metric]?data.team_changes[metric].teams.find(c=>c.team===t.team):t.metrics[metric].first_vs_all_subsequent.differences[0];
      return [t.team_name+(t.games===11?' *':''),...t.metrics[metric].groups.map(groupText),`${signed(c.difference*scale)} [${range(c.ci95,scale)}]`];
    }));
    const val=(g,c=false)=>Number((g.estimate*(c?1:100)).toFixed(1));
    const team=data.teams.find(t=>t.team===teamId);
    const scores=scoreView==='observed'?data.league.scoring.groups:data.adjusted.scoring.groups;
    const expectedBars=[...data.league.early_huck.groups.map(g=>val(g)),
      ...data.throw_windows.flatMap(w=>[val(w.groups[0]),val(w.groups[1])]),
      ...[0,1,2].flatMap(i=>[val(data.league.throws_goal.groups[i],true),val(data.league.throws_turnover.groups[i],true)]),
      ...scores.map(g=>val(g)),...team.metrics[metric].groups.filter(g=>g.n>0&&g.estimate!=null).map(g=>val(g,count)),
      ...data.league.huck_completion.groups.map(g=>val(g)),...data.follow_up.break_league.groups.map(g=>val(g))];
    assert.deepEqual(actual.bars.map(b=>b.value),expectedBars);
    assert.equal(actual.charts,7);
    assert.equal(await page.locator('[data-axis-x]').count(),7);
    assert.equal(await page.locator('[data-axis-y]').count(),7);
    assert.equal(await page.locator('select').nth(3).locator('option').count(),pool==='all'?22:12);
    assert.deepEqual(actual.rows[6], [...data.follow_up.playoff_summary].sort((a,b)=>a.team_name.localeCompare(b.team_name)).map(t=>[t.team_name,...['throws_goal','throws_turnover','scoring','early_huck'].map(k=>{
      const m=t.metrics[k];return `${k.startsWith('throws')?m.first.toFixed(1):pct(m.first)} (${m.first_n}) → ${k.startsWith('throws')?m.subsequent.toFixed(1):pct(m.subsequent)} (${m.subsequent_n})`;
    })]));
    assert(actual.text.includes('It does not adjust for which passes are centering passes.'));
    assert(actual.text.includes('11.5%')&&actual.text.includes('20.9%'));
  } else {
    const c = data.cases.find(c => c.id === choice);
    assert.deepEqual(actual.rows[0], c.throws.map(t => [String(t.n), t.from+' → '+t.to, t.outcome+(t.huck?' · Huck':'')]));
    assert.equal(actual.charts, 1);
    if (['C','E'].includes(choice)) assert(actual.text.toLowerCase().includes('not a centering pass'));
    if (choice==='D') assert(actual.text.includes('Your review: throw 1 is a centering pass'));
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
      if (name.includes('oline-regain')) {
        const metrics=await page.locator('select').nth(2).locator('option').evaluateAll(ns=>ns.map(n=>n.value));
        for (const pool of ['playoffs','all']) {
          await page.locator('select').nth(1).selectOption(pool);
          const teams=await page.locator('select').nth(3).locator('option').evaluateAll(ns=>ns.map(n=>n.value));
          for (const metric of metrics) {
            await page.locator('select').nth(2).selectOption(metric);
            for (const team of teams) {
              await page.locator('select').nth(3).selectOption(team);
              results.push({...await verify(page,name,null),pool,metric,team});
            }
          }
        }
        await page.locator('select').nth(3).selectOption('hustle');
        await page.locator('select').nth(1).selectOption('playoffs');
        assert.equal(await page.locator('select').nth(3).inputValue(),'spiders','Non-playoff selection must reset when switching to playoff teams');
        await page.locator('select').nth(2).selectOption('throws_goal');
      }
      if (options.length) await firstSelect.selectOption(options[0]);
      const summary = page.locator('summary').first();
      if (await summary.count()) {
        await summary.click();
        assert.equal(await page.locator('details').first().getAttribute('open'), '');
        assert(await page.getByText('UFA', {exact:false}).count() > 0);
      }
      await page.screenshot({path:path.join(output, name + '-wide.png'), fullPage:true});
      if (name.includes('oline-regain')) {
        for (const id of ['league','teams','huck-outcomes','breaks','paper']) {
          await page.locator('#'+id).screenshot({path:path.join(output,name+'-'+id+'-wide.png')});
        }
      }
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
