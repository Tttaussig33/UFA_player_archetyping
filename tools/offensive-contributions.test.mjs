import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {contributionDirectory,contributionPlot,playerContributions,intervalText} from '../src/content/dashboard/contribution-model.js';

const data=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const rows=data.queries.offensiveContributions.rows,baselines=data.queries.contributionBaselines.rows;

test('contributions cover the full cohort and scoring overlaps the directional partition',()=>{
  assert.equal(rows.length,747);
  const ids=new Set(rows.map(r=>r.playerId));assert.equal(ids.size,249);
  for(const id of ids){
    const parts=playerContributions(rows,id,baselines);
    assert.equal(parts.length,3);
    assert.equal(parts[0].attempts+parts[1].attempts,parts[0].totalPasses);
    assert.ok(Math.abs(parts[0].share+parts[1].share-1)<1e-12);
    assert.ok(parts[2].attempts<=parts[0].totalPasses);
    assert.ok(parts[2].assists<=parts[2].completions);
  }
  const score=baselines.find(r=>r.role==='score');
  assert.equal(score.completions-score.assists,42);
});

test('role sample, team and name filters coordinate table and plot without moving baseline',()=>{
  const unchanged=JSON.stringify(baselines);
  const scorers=contributionDirectory(rows,{role:'score'});
  assert.equal(scorers.length,95);
  assert.ok(scorers.every(r=>r.attempts>=20));
  assert.ok(contributionDirectory(rows,{role:'redistribute',team:'hustle'}).every(r=>r.teamId==='hustle'));
  assert.equal(contributionDirectory(rows,{search:'spencer lofink'})[0].name,'Spencer Lofink');
  assert.equal(contributionDirectory(rows,{search:' de marree '})[0].name,'Daan De Marrée');
  assert.equal(contributionDirectory(rows,{role:'score',minimum:50}).length,11);
  assert.deepEqual(contributionDirectory(rows,{search:'no player xyz'}),[]);
  assert.equal(JSON.stringify(baselines),unchanged);
});

test('missing outcomes remain missing, sorting is explicit, and small-sample intervals are unavailable',()=>{
  const fake={...rows[0],playerId:'empty',name:'Empty',attempts:0,share:0,cpoePp:null,lowerPp:null,upperPp:null};
  const sorted=contributionDirectory([fake,rows[0]],{minimum:0,sort:'cpoePp'});
  assert.equal(sorted.at(-1).playerId,'empty');
  assert.equal(contributionPlot(sorted).length,1);
  assert.equal(intervalText(fake),'Interval unavailable');
  for(const r of rows){
    if(r.attempts<20||r.roleGames<6)assert.equal(r.lowerPp,null);
    if(r.lowerPp!==null)assert.ok(r.lowerPp<=r.upperPp);
  }
});

test('fixed cohort checks disclose thin scoring-outcome evidence and complementary shares',()=>{
  const study=data.queries.contributionStudy.rows;
  assert.equal(study.find(r=>r.role==='score').outcomePlayers,13);
  assert.equal(study[0].shareSpearman,study[1].shareSpearman);
  assert.ok(study.every(r=>r.sharePlayers===211));
});
