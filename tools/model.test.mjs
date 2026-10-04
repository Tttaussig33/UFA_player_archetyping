import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {ZONES,fieldZones,zoneFor,zoneBuckets,rankZone} from '../src/content/dashboard/model.js';
const snapshot=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=snapshot.queries.events.rows,calls=snapshot.queries.callahans.rows;
test('zones cover both end zones and assign shared boundaries consistently for either metric',()=>{
 assert.equal(ZONES.length,12);
 assert.equal(zoneFor(-26.67,20,'throw'),'left-build');
 assert.equal(zoneFor(-15,40,'throw'),'center-build');
 assert.equal(zoneFor(15,60,'throw'),'right-attack');
 assert.equal(zoneFor(0,100,'throw'),'ez-right');
 assert.equal(zoneFor(0,19.99,'throw'),'own-endzone');
 assert.equal(zoneFor(0,0,'receive'),'own-endzone');
 assert.equal(zoneFor(0,20,'receive'),'center-init');
 assert.equal(zoneFor(0,-.01),null);
 assert.equal(zoneFor(0,120.01),null);
 assert.equal(zoneFor(-.01,100,'receive'),'ez-left');
 assert.equal(zoneFor(0,100,'receive'),'ez-right');
 assert.equal(zoneFor(-20,110,'receive'),'ez-deep');
 assert.equal(zoneFor(26.66,120,'receive'),'ez-deep');
 assert.equal(zoneFor(null,100,'receive'),null);
 assert.equal(zoneFor(50,30,'throw'),null);
});
test('all 22 teams retain every eligible event and reconcile full-field totals for both roles',()=>{
 for(const team of snapshot.queries.teams.rows){
  const e=events.filter(e=>e.team===team.id&&e.phase==='Regular season');
  assert.ok(e.length>1000,team.name);
  for(const role of ['throw','receive']){
   const eligible=e.filter(r=>role==='throw'||(r.receiver&&(r.complete||r.drop)));
   const buckets=zoneBuckets(e,[],role),mapped=Object.values(buckets).flat();
   assert.equal(mapped.length,eligible.length,`${team.id}/${role}`);
   assert.equal(new Set(mapped.map(r=>r.id)).size,mapped.length);
   const ranks=ZONES.flatMap(z=>rankZone(buckets[z.id],role));
   assert.ok(ranks.every(p=>p.count===p.events.length&&p.completed<=p.count));
   const credit=role==='throw'?'throwAec':'receiveAec',person=role==='throw'?'thrower':'receiver';
   const expected=eligible.filter(r=>r[person]&&r[person]!=='unknown').reduce((sum,r)=>sum+(r[credit]??0),0);
   assert.ok(Math.abs(ranks.reduce((sum,p)=>sum+(p.aec??0),0)-expected)<1e-8);
   assert.ok(buckets['own-endzone'].length>0);
  }
 }
});
test('receiving uses destinations and receiver credit, including drops but excluding throwaways',()=>{
 const rows=[
  {id:'complete',thrower:'a',receiver:'b',tx:0,ty:10,rx:0,ry:30,complete:true,drop:false,throwAec:.3,receiveAec:.3},
  {id:'drop',thrower:'c',receiver:'d',tx:20,ty:45,rx:-20,ry:85,complete:false,drop:true,throwAec:0,receiveAec:-.4},
  {id:'away',thrower:'c',receiver:'d',tx:20,ty:45,rx:-20,ry:85,complete:false,drop:false,throwAec:-.5,receiveAec:0},
 ];
 const t=zoneBuckets(rows,[],'throw'),r=zoneBuckets(rows,[],'receive');
 assert.equal(rankZone(t['own-endzone'],'throw')[0].id,'a');
 assert.equal(rankZone(r['center-init'],'receive')[0].id,'b');
 assert.equal(t['right-build'].length,2);assert.equal(r['left-attack'].length,1);
 assert.equal(rankZone(r['left-attack'],'receive')[0].aec,-.4);
});
test('Callahans replace only the selected bottom panel and never enter offensive aEC',()=>{
 for(const role of ['throw','receive']){
  const ordinary=zoneBuckets(events,calls,role),defensive=zoneBuckets(events,calls,role,'callahan');
  assert.deepEqual(defensive['own-endzone'],calls);
  for(const zone of ZONES.filter(z=>z.id!=='own-endzone'))assert.deepEqual(ordinary[zone.id],defensive[zone.id]);
  assert.equal(fieldZones(role,'callahan').find(z=>z.id==='own-endzone').role,'callahan');
  assert.ok(fieldZones(role).every(z=>z.role===role));
 }
});
test('Original preserves mixed roles, role-specific goal-line edges, and defensive bottom credit',()=>{
 const rows=[
  {id:'goal-line',thrower:'a',receiver:'b',tx:0,ty:100,rx:-5,ry:100,complete:true,throwAec:.2,receiveAec:.2},
  {id:'drop',thrower:'a',receiver:'c',tx:0,ty:75,rx:0,ry:115,drop:true,throwAec:0,receiveAec:-.4},
  {id:'away',thrower:'a',receiver:'c',tx:0,ty:75,rx:0,ry:115,throwAec:-.5,receiveAec:0},
  {id:'backfield',thrower:'a',receiver:'b',tx:0,ty:10,rx:0,ry:30,complete:true,throwAec:.1,receiveAec:.1},
 ];
 const defender=[{id:'defense',player:'d',aec:.9}];
 const zones=fieldZones('original'),buckets=zoneBuckets(rows,defender,'original');
 assert.equal(zones.filter(z=>z.role==='receive').length,3);
 assert.equal(zones.filter(z=>z.role==='throw').length,8);
 assert.equal(zones.filter(z=>z.role==='callahan').length,1);
 assert.deepEqual(buckets['own-endzone'],defender);
 assert.deepEqual(buckets['center-red'].map(e=>e.id),['goal-line']);
 assert.deepEqual(buckets['ez-left'].map(e=>e.id),['goal-line']);
 assert.deepEqual(buckets['ez-deep'].map(e=>e.id),['drop']);
 assert.equal(rankZone(buckets['center-attack'],'throw')[0].aec,-.5);
 assert.equal(rankZone(buckets['ez-deep'],'receive')[0].aec,-.4);
 assert.ok(!Object.values(buckets).flat().some(e=>e.id==='backfield'));
 assert.deepEqual(zoneBuckets(rows,defender,'original','callahan'),buckets);
 assert.deepEqual(fieldZones('original','callahan'),zones);
});
test('Original maps every team to the original throwing, receiving, and Callahan populations',()=>{
 for(const team of snapshot.queries.teams.rows){
  const e=events.filter(e=>e.team===team.id),c=calls.filter(e=>e.team===team.id);
  const zones=fieldZones('original'),buckets=zoneBuckets(e,c,'original');
  for(const zone of zones){
   const expected=zone.role==='callahan'?c:e.filter(row=>{
    const receiving=zone.role==='receive',x=receiving?row.rx:row.tx,y=receiving?row.ry:row.ty;
    return (!receiving||(row.receiver&&(row.complete||row.drop)))
      &&x>=(zone.x0===-26.65?-26.67-1e-8:zone.x0)&&(zone.x1===26.65?x<=26.67+1e-8:x<zone.x1)
      &&y>=zone.y0&&((!receiving&&zone.y1===100)||zone.y1===120?y<=zone.y1:y<zone.y1);
   });
   assert.deepEqual(buckets[zone.id].map(r=>r.id),expected.map(r=>r.id),`${team.id}/${zone.id}`);
  }
 }
});
test('Original restores the first Boston map’s receivers, midfield throwers, and Callahan leader',()=>{
 const e=events.filter(e=>e.team==='glory'&&e.phase==='Regular season');
 const c=calls.filter(e=>e.team==='glory'&&e.phase==='Regular season');
 const buckets=zoneBuckets(e,c,'original');
 for(const [zone,role,id,value] of [
  ['ez-deep','receive','tedmonds','4.05'],
  ['center-red','throw','ograff','10.76'],
  ['own-endzone','callahan','sfisherol','0.93'],
 ]){
  const [leader]=rankZone(buckets[zone],role);
  assert.equal(leader.id,id);assert.equal(leader.aec.toFixed(2),value);
 }
});
test('Boston bottom-end-zone and midfield receiving match independent coordinate sums',()=>{
 const e=events.filter(e=>e.team==='glory'&&e.phase==='Regular season');
 const [thrower]=rankZone(zoneBuckets(e,[],'throw')['own-endzone'],'throw');
 assert.equal(thrower.id,'rdinger');assert.equal(thrower.count,118);assert.equal(thrower.completed,113);assert.equal(thrower.aec.toFixed(2),'4.56');
 const receiving=zoneBuckets(e,[],'receive');
 const [receiver]=rankZone(receiving['own-endzone'],'receive');
 assert.equal(receiver.id,'rdinger');assert.equal(receiver.count,75);assert.equal(receiver.aec.toFixed(2),'1.47');
 const [middle]=rankZone(receiving['center-build'],'receive');
 assert.equal(middle.id,'tdecraene');assert.equal(middle.count,130);assert.equal(middle.aec.toFixed(2),'3.99');
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
