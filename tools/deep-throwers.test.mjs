import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildDeepThrower,buildHuckSetups,deepThrowerComparison,precedingPasses,priorPassDirection,selectHucks,sequenceSource,bestReleaseZone,completionInterval,rankDeepThrowers} from '../src/content/dashboard/deep-thrower-model.js';

const pass=(id,overrides={})=>({id,game:'game-1',team:'team-a',quarter:1,point:1,possession:1,
  possessionThrow:1,eventSequence:10,thrower:'a',receiver:'b',tx:0,ty:25,rx:0,ry:30,
  complete:true,stall:false,throwAec:.1,...overrides});
const prior=pass('prior');
const huck=pass('huck',{thrower:'b',receiver:'c',possessionThrow:2,eventSequence:12,tx:0,ty:30,rx:0,ry:80,throwAec:.4});

test('verified sequences require the same possession and consecutive throw order, not adjacent event numbers',()=>{
  assert.equal(precedingPasses([huck,prior]).get('huck'),prior);
  for(const changes of [{game:'other'},{team:'other'},{quarter:2},{point:2},{possession:2},
    {possessionThrow:3},{possessionThrow:null},{eventSequence:10},{eventSequence:null}]) {
    assert.equal(precedingPasses([prior,{...huck,...changes}]).has('huck'),false,JSON.stringify(changes));
  }
  for(const changes of [{complete:false},{stall:true},{receiver:'other'},{receiver:null}]) {
    assert.equal(precedingPasses([{...prior,...changes},huck]).has('huck'),false);
  }
});

test('ambiguous throw orders or event sequence numbers cannot create a prior-pass match',()=>{
  assert.equal(precedingPasses([prior,{...prior,id:'duplicate'},huck]).has('huck'),false);
  assert.equal(precedingPasses([prior,huck,{...huck,id:'duplicate'}]).has('huck'),false);
  const duplicateSequence=pass('ambiguous',{possessionThrow:3,eventSequence:12});
  assert.equal(precedingPasses([prior,huck,duplicateSequence]).has('huck'),false);
});

test('incompletions and unnamed targets remain huck attempts; stalls and unknown geometry do not',()=>{
  const rows=[prior,huck,pass('fail',{...huck,id:'fail',point:2,receiver:null,complete:false,throwAec:-.7,possessionThrow:1}),
    pass('stall',{point:3,thrower:'b',receiver:'c',stall:true,rx:0,ry:90}),pass('missing',{point:4,thrower:'b',receiver:'c',rx:null})];
  const model=buildDeepThrower(rows,'b');
  assert.equal(model.attempts,2);assert.equal(model.completed,1);assert.equal(model.failed,1);
  assert.equal(model.rate,.5);assert.equal(model.huckShare,1); // Two hucks / two throws with geometry.
  assert.equal(model.throws.length,3);assert.equal(model.locatedThrows.length,2);
  assert.equal(model.catches.length,1);
  assert.equal(selectHucks(model,{kind:'receive',zoneId:'center-init'}).length,1);
});

test('zone boundaries are exhaustive and disjoint; all catches and before-huck catches have separate denominators',()=>{
  const rows=[prior,huck,pass('extra-catch',{point:2,rx:-15,ry:40}),pass('dropped',{point:3,receiver:'b',complete:false,drop:true}),
    pass('sideline-huck',{point:4,thrower:'b',receiver:'c',tx:26.67,ty:20,rx:0,ry:90})];
  const model=buildDeepThrower(rows,'b');
  assert.equal(model.zones.reduce((sum,z)=>sum+z.attempts,0),model.attempts);
  assert.equal(model.zones.reduce((sum,z)=>sum+z.catches,0),2);
  assert.equal(model.zones.reduce((sum,z)=>sum+z.beforeHuck,0),1);
  assert.equal(model.zones.find(z=>z.id==='center-init').catchShare,.5);
  assert.equal(model.zones.find(z=>z.id==='center-init').beforeShare,1);
  assert.equal(model.zones.find(z=>z.id==='right-build').attempts,1);
  assert.equal(model.zones.find(z=>z.id==='center-build').catches,1);
  assert.equal(model.zones.find(z=>z.id==='ez-deep').rate,null);
});

test('missing aEC does not remove huck attempts; no-attempt rates are undefined and small samples do not win a zone recommendation',()=>{
  const model=buildDeepThrower([prior,{...huck,throwAec:null}],'b');
  assert.equal(model.attempts,1);assert.equal(model.completed,1);assert.equal(model.rate,1);
  assert.equal(bestReleaseZone(model,5),null);assert.equal(bestReleaseZone(model,1).id,'center-init');
  assert.deepEqual(completionInterval(0,0),[null,null]);
  const interval=completionInterval(1,1);assert.ok(interval[0]<.21&&interval[1]<=1);
  const empty=buildDeepThrower([],'b');assert.equal(empty.rate,null);assert.equal(empty.huckShare,null);
});

test('source inspection includes each original huck and verified prior pass only once',()=>{
  const rows=[prior,huck],links=precedingPasses(rows);
  assert.deepEqual(sequenceSource([huck],links),[prior,huck]);
  assert.deepEqual(sequenceSource([prior,huck],links),[prior,huck]);
  assert.equal(deepThrowerComparison(rows).find(p=>p.id==='b').huckShare,1);
});

const snapshot=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url),'utf8'));
const events=snapshot.queries.events.rows;
test('2026 snapshot reconciles Atkins to 53 attempts and 45 completions; regular-season filter gives 28 completions',()=>{
  const model=buildDeepThrower(events,'aatkins');
  assert.equal(model.attempts,53);assert.equal(model.completed,45);assert.equal(model.pairs.length,44);
  const regular=buildDeepThrower(events.filter(e=>e.phase==='Regular season'),'aatkins');
  assert.equal(regular.completed,28);
  assert.equal(model.zones.reduce((sum,z)=>sum+z.attempts,0)+model.unmappedReleases,53);
  assert.equal(model.zones.reduce((sum,z)=>sum+z.beforeHuck,0)+model.unmappedLinked,44);
  assert.equal(model.zones.reduce((sum,z)=>sum+z.catches,0)+model.unmappedCatches,model.catches.length);
  assert.equal(new Set(model.pairs.map(p=>p.previous.id)).size,44);
});

test('every league comparison row reconciles to the selected player and scope, including line and phase filters',()=>{
  for(const scoped of [events,events.filter(e=>e.team==='hustle'&&e.phase==='Regular season'&&e.line==='O-line')]) {
    const links=precedingPasses(scoped),comparison=deepThrowerComparison(scoped);
    assert.equal(comparison.reduce((sum,p)=>sum+p.attempts,0),scoped.filter(e=>e.thrower&&e.thrower!=='unknown'&&!e.stall&&
      [e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)&&Math.hypot(e.rx-e.tx,e.ry-e.ty)>40&&e.ry-e.ty>30).length);
    for(const player of comparison.filter(p=>p.attempts>=20)) {
      const model=buildDeepThrower(scoped,player.id,links);
      assert.equal(player.attempts,model.attempts);assert.equal(player.completed,model.completed);
      assert.equal(player.rate,model.rate);assert.equal(player.huckShare,model.huckShare);
      for(const zone of player.zones) {
        const detail=model.zones.find(z=>z.id===zone.id);
        assert.equal(zone.attempts,detail.attempts);assert.equal(zone.completed,detail.completed);
        assert.equal(zone.rate,detail.rate);
      }
      assert.ok(model.pairs.length<=model.attempts);
    }
  }
});

test('zone leaderboards rank the chosen location and enforce separate player and zone samples',()=>{
  const rows=[];
  const add=(thrower,ty,completed,attempts)=>{
    for(let i=0;i<attempts;i++)rows.push(pass(`rank-${rows.length}`,{thrower,tx:0,ty,rx:0,ry:ty+50,complete:i<completed}));
  };
  add('a',30,8,10);add('a',10,0,10);
  add('b',30,6,6);add('b',10,14,14);
  add('c',30,4,4);add('c',10,16,16);
  add('d',30,3,3);
  const players=deepThrowerComparison(rows);
  assert.deepEqual(rankDeepThrowers(players).map(p=>p.id),['b','c','a']);
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-init'}).map(p=>p.id),['b','a']);
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-init',minimumZone:10}).map(p=>p.id),['a']);
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-init',sort:'attempts'}).map(p=>p.id),['a','b']);
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-init',minimumPlayer:1,minimumZone:3}).map(p=>p.id),['b','c','d','a']);
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-red'}),[]);
  assert.equal(players.find(p=>p.id==='c').zones.find(z=>z.id==='center-init').attempts,4);
  assert.deepEqual(rankDeepThrowers(players,{minimumRate:.7}).map(p=>p.id),['b','c']);
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-init',minimumRate:.8}).map(p=>p.id),['b','a'],'The rate floor is inclusive and uses the ranked zone, not overall rate');
  assert.deepEqual(rankDeepThrowers(players,{zoneId:'center-init',minimumRate:.81,sort:'attempts'}).map(p=>p.id),['b'],'Volume sorting cannot bypass the completion filter');
});

test('incoming direction groups use disc geometry, with explicit boundaries and unclassified cases',()=>{
  const p=changes=>({...prior,tx:0,ty:40,...changes});
  assert.equal(priorPassDirection(p({rx:5,ry:46})),'forward');
  assert.equal(priorPassDirection(p({rx:-5,ry:34})),'backward');
  assert.equal(priorPassDirection(p({rx:-5,ry:45})),'lateral');
  assert.equal(priorPassDirection(p({rx:5,ry:35})),'lateral');
  assert.equal(priorPassDirection(p({rx:5,ry:40})),'lateral');
  assert.equal(priorPassDirection(p({rx:0,ry:40})),'unclassified');
  assert.equal(priorPassDirection(p({rx:null,ry:40})),'unclassified');
  assert.equal(priorPassDirection(null),'unclassified');
});

test('setup tendencies retain non-hucks in the choice denominator, unknown setups, and exact source drilldowns',()=>{
  const short=pass('short',{thrower:'b',point:2,possessionThrow:2,eventSequence:22,tx:0,ty:30,rx:0,ry:35});
  const shortPrior=pass('short-prior',{point:2,eventSequence:20});
  const unknown=pass('unknown',{thrower:'b',point:3,tx:20,ty:30,rx:20,ry:80,complete:false});
  const missing=pass('missing',{thrower:'b',point:4,rx:null});
  const rows=[prior,huck,shortPrior,short,unknown,missing],links=precedingPasses(rows),model=buildDeepThrower(rows,'b',links);
  const setups=buildHuckSetups(model,links),forward=setups.groups.find(s=>s.id==='forward');
  assert.equal(setups.nextThrows,3);assert.equal(setups.missingGeometry,1);
  assert.equal(setups.attempts,2);assert.equal(setups.completed,1);
  assert.equal(forward.nextThrows,2);assert.equal(forward.huckShare,.5);assert.equal(forward.rate,1);
  assert.equal(setups.groups.find(s=>s.id==='unclassified').attempts,1);
  assert.equal(setups.groups.find(s=>s.id==='lateral').rate,null);
  assert.deepEqual(selectHucks(model,{kind:'setup',setupId:'forward',zoneId:'all'}),[huck]);
  assert.deepEqual(selectHucks(model,{kind:'setup',setupId:'forward',zoneId:'right-build'}),[]);
  assert.deepEqual(selectHucks(model,{kind:'setup',setupId:'unclassified',zoneId:'right-build'}),[unknown]);
  assert.equal(buildHuckSetups(model,links,'center-init').nextThrows,2);
  assert.equal(new Set(sequenceSource(setups.throws,links).map(e=>e.id)).size,6);
});

test('snapshot setup groups reconcile to all hucks and retain their release-zone and phase scopes',()=>{
  for(const scoped of [events,events.filter(e=>e.phase==='Regular season')]) {
    const links=precedingPasses(scoped),model=buildDeepThrower(scoped,'aatkins',links);
    for(const zone of ['all','center-init','right-build','center-red']) {
      const setups=buildHuckSetups(model,links,zone);
      assert.equal(setups.groups.reduce((n,s)=>n+s.nextThrows,0),setups.nextThrows);
      assert.equal(setups.groups.reduce((n,s)=>n+s.attempts,0),setups.attempts);
      assert.equal(setups.groups.reduce((n,s)=>n+s.completed,0),setups.completed);
      assert.equal(setups.attempts,zone==='all'?model.attempts:model.zones.find(z=>z.id===zone).attempts);
      for(const s of setups.groups)assert.deepEqual(selectHucks(model,{kind:'setup',setupId:s.id,zoneId:zone}),s.hucks);
    }
  }
  const model=buildDeepThrower(events,'aatkins'),setups=buildHuckSetups(model,precedingPasses(events));
  assert.deepEqual(setups.groups.map(s=>[s.id,s.nextThrows,s.attempts,s.completed]),[
    ['forward',163,22,19],['lateral',236,17,16],['backward',36,5,3],['unclassified',116,9,7],
  ]);
});
