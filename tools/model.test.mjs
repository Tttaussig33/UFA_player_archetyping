import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {ZONES,zoneFor,zoneBuckets,rankZone} from '../src/content/dashboard/model.js';
const snapshot=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=snapshot.queries.events.rows,calls=snapshot.queries.callahans.rows;
test('zones assign shared edges once, include rounded sidelines, and preserve own-end-zone exclusion',()=>{
 assert.equal(ZONES.length,12);
 assert.equal(zoneFor(-26.67,20,'throw'),'left-build');
 assert.equal(zoneFor(-15,40,'throw'),'center-build');
 assert.equal(zoneFor(15,60,'throw'),'right-attack');
 assert.equal(zoneFor(0,100,'throw'),'center-red');
 assert.equal(zoneFor(0,19.99,'throw'),null);
 assert.equal(zoneFor(-.01,100,'receive'),'ez-left');
 assert.equal(zoneFor(0,100,'receive'),'ez-right');
 assert.equal(zoneFor(-20,110,'receive'),'ez-deep');
 assert.equal(zoneFor(26.66,120,'receive'),'ez-deep');
 assert.equal(zoneFor(null,100,'receive'),null);
 assert.equal(zoneFor(50,30,'throw'),null);
});
test('all 22 teams have populated reference maps with all available events, without sampling',()=>{
 for(const team of snapshot.queries.teams.rows){
  const e=events.filter(e=>e.team===team.id&&e.phase==='Regular season');
  const c=calls.filter(e=>e.team===team.id&&e.phase==='Regular season');
  const buckets=zoneBuckets(e,c);
  assert.ok(e.length>1000,team.name);
  for(const z of ZONES.filter(z=>z.role!=='callahan')){
   const ranks=rankZone(buckets[z.id],z.role);assert.ok(ranks.length>0,`${team.id}/${z.id}`);
   assert.ok(ranks.every(p=>p.count===p.events.length));
   assert.ok(ranks.every(p=>p.completed<=p.count));
  }
  const throws=ZONES.filter(z=>z.role==='throw').flatMap(z=>buckets[z.id]);
  assert.equal(throws.length,e.filter(e=>e.ty>=20&&e.ty<=100).length);
  assert.equal(new Set(throws.map(e=>e.id)).size,throws.length);
 }
});
test('null aEC is unknown rather than zero, while its event remains available',()=>{
 const [p]=rankZone([{id:'a',thrower:'person',throwAec:null,complete:true}],'throw');
 assert.equal(p.aec,null);assert.equal(p.scored,0);assert.equal(p.count,1);
});
test('source player metrics reconcile to supplied per-game totals',()=>{
 const audit=JSON.parse(fs.readFileSync(new URL('../data/validation.json',import.meta.url)));
 assert.equal(audit.teams,22);assert.equal(audit.regularSeasonGames,131);
 assert.ok(audit.playerMetricChecks>=2304);assert.equal(audit.metricDisagreements.length,0);
 assert.ok(audit.maxPlayerMetricDelta<1e-8);
 assert.equal(new Set(events.map(e=>e.id)).size,events.length);
});
test('the reference Callahan leader reproduces its 1.86 aEC with the named defender',()=>{
 const klane=rankZone(calls.filter(e=>e.date<='2026-07-09'),'callahan').find(p=>p.id==='jklane');
 assert.equal(klane.count,2);assert.equal(klane.aec.toFixed(2),'1.86');
 assert.ok(calls.every(c=>c.aec>=0&&c.player));
});
test('Boston initiation stays consistent with independently inspected raw input',()=>{
 const e=events.filter(e=>e.team==='glory'&&e.phase==='Regular season');
 const [top]=rankZone(zoneBuckets(e,[])['center-init'],'throw');
 assert.equal(top.id,'rdinger');assert.equal(top.count,130);assert.equal(top.completed,125);assert.equal(top.aec.toFixed(2),'8.87');
});
