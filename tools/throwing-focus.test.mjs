import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {focusModel,focusDirectory,throwResults,directionPoint} from '../src/content/dashboard/throwing-focus-model.js';

const data=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const original=JSON.parse(fs.readFileSync(new URL('../data/source-api/leaderboard-2026-2026-11-03.json',import.meta.url))).data;
const summaries=data.queries.shownSpaceThrowers.rows,events=data.queries.events.rows;
const close=(a,b,label)=>assert.ok(Math.abs(a-b)<1e-7,`${label}: ${a} vs ${b}`);
const pass=(id,distance,angle,extra={})=>({id,thrower:'test',tx:0,ty:0,rx:0,ry:distance,throwAngle:angle,complete:true,throwAec:.1,...extra});

test('length edges partition every pass once; a drop is incomplete and a stall is excluded',()=>{
  const rows=[pass('zero',0,-90),pass('short',9.9,0),pass('ten',10,30),pass('twenty',20,60),
    pass('forty',40,90,{complete:false,drop:true,throwAec:0}),pass('stall',0,0,{stall:true,complete:false,throwAec:-1})];
  const m=focusModel(rows,'test');
  assert.deepEqual(m.groups.map(g=>g.attempts),[2,1,1,1]);
  assert.deepEqual(m.groups.flatMap(g=>g.rows.map(e=>e.id)),rows.slice(0,5).map(e=>e.id));
  assert.equal(m.results.attempts,5);
  assert.equal(m.results.completed,4);
  close(m.results.completion,.8,'completion');
  close(m.results.aec,.4,'source aEC');
  assert.equal(focusModel(rows,'test','length','40plus').results.completed,0);
  assert.equal(focusModel(rows,'test','length','40plus').results.aec,0);
  assert.ok(!JSON.stringify(m.displayRows).includes('Infinity'));
});

test('direction normalizes negative angles and omits stationary or unlocated throws',()=>{
  const rows=[pass('forward',1,0),pass('edge',1,30),pass('right',1,-90),pass('wrap',1,360),
    pass('stationary',0,-90),pass('missing-angle',1,null),pass('missing-coordinate',1,45,{rx:null})];
  const m=focusModel(rows,'test','direction');
  assert.equal(m.eligible.length,4);
  assert.equal(m.excluded,3);
  assert.deepEqual(m.groups[0].rows.map(e=>e.id),['forward','wrap']);
  assert.equal(m.groups[1].rows[0].id,'edge');
  assert.equal(m.groups[9].rows[0].id,'right');
  assert.equal(focusModel(rows,'test','direction','9').results.attempts,1);
  close(directionPoint(0,100)[1],80,'forward is up');
  close(directionPoint(90,100)[0],80,'positive 90 degrees is left');
  close(directionPoint(270,100)[0],280,'negative 90 degrees is right');
});

test('missing values remain unavailable, while real zero aEC is retained',()=>{
  assert.equal(throwResults([]).completion,null);
  assert.equal(throwResults([]).aec,null);
  assert.equal(throwResults([pass('missing',1,0,{throwAec:null})]).aec,null);
  assert.equal(throwResults([pass('zero',1,0,{throwAec:0})]).aec,0);
  assert.equal(throwResults([pass('missing',1,0,{throwAec:null})]).missingAec,1);
});

test('all named throwers use unchanged official aEC and LC, with source count differences retained',()=>{
  const source=new Map(original.map(p=>[p.PlayerID,p]));
  const named=new Set(events.map(e=>e.thrower).filter(id=>id&&id!=='unknown'));
  assert.equal(summaries.length,747);
  assert.deepEqual(new Set(summaries.map(p=>p.id)),named);
  assert.equal(new Set(summaries.map(p=>p.team)).size,22);
  assert.equal(summaries.filter(p=>p.sourceAttempts!==p.recordedAttempts).length,8);
  assert.equal(summaries.filter(p=>p.sourceCompletions!==p.recordedCompletions).length,5);
  for(const p of summaries){
    const s=source.get(p.id),local=events.filter(e=>e.thrower===p.id);
    assert.equal(p.throwerAec,s.thrower_aec,p.name);
    assert.equal(p.lagContribution,s.lag_contribution,p.name);
    close(p.throwerAec,local.reduce((n,e)=>n+(e.throwAec??0),0),p.name);
    assert.equal(p.sourceAttempts,s.ThrowAttempts);
    assert.equal(p.recordedAttempts,local.filter(e=>!e.stall).length);
    assert.equal(p.recordedCompletions,local.filter(e=>!e.stall&&e.complete).length);
  }
  assert.equal(focusDirectory(summaries,'spencer lofink')[0].name,'Spencer Lofink');
  assert.equal(focusDirectory(summaries,'de marree')[0].name,'Daan De Marrée');
  assert.ok(focusDirectory(summaries,'Seattle').every(p=>p.team==='cascades'));
});

test('both views reconcile every displayed group and selection to its exact source passes',()=>{
  for(const p of summaries){
    const local=events.filter(e=>e.thrower===p.id);
    for(const view of ['length','direction']){
      const m=focusModel(local,p.id,view),ids=m.groups.flatMap(g=>g.rows.map(e=>e.id));
      assert.equal(ids.length,m.eligible.length,p.name);
      assert.equal(new Set(ids).size,ids.length,p.name);
      assert.equal(m.groups.reduce((n,g)=>n+g.completed,0),m.results.completed,p.name);
      close(m.groups.reduce((n,g)=>n+(g.aec??0),0),m.results.aec??0,p.name);
      for(const group of m.groups){
        const selected=focusModel(local,p.id,view,group.id);
        assert.deepEqual(selected.rows,group.rows,p.name);
        assert.deepEqual(selected.results,throwResults(group.rows),p.name);
      }
    }
  }
});
