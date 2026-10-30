import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {observedThrowingTraits,throwerComparison,throwerDirectory,PASSING_TRAITS} from '../src/content/dashboard/thrower-profile-model.js';

const data=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const analysis=JSON.parse(fs.readFileSync(new URL('../analysis/thrower_article_comparison.json',import.meta.url)));
const profiles=data.queries.throwerProfiles.rows,reference=data.queries.throwerReference.rows;
const close=(a,b,label)=>assert.ok(Math.abs(a-b)<1e-9,`${label}: ${a} vs ${b}`);

test('directory includes every eligible thrower, including players without 100 catches',()=>{
  assert.equal(profiles.length,249);
  assert.deepEqual(profiles.map(p=>p.id).sort(),analysis.allProfiles.map(p=>p.id).sort());
  assert.ok(profiles.length>analysis.examples.length);
  assert.equal(new Set(profiles.map(p=>p.team)).size,22);
  assert.ok(profiles.some(p=>p.catches<100));
  assert.ok(profiles.every(p=>p.throws>=100&&p.games>=6));
});

test('all 249 profiles reconcile to the website pass snapshot',()=>{
  const byPlayer=new Map();
  for(const e of data.queries.events.rows){
    if(e.phase!=='Regular season'||!e.thrower)continue;
    if(!byPlayer.has(e.thrower))byPlayer.set(e.thrower,[]);
    byPlayer.get(e.thrower).push(e);
  }
  for(const p of profiles){
    const events=byPlayer.get(p.id),passes=events.filter(e=>!e.stall),scored=passes.filter(e=>Number.isFinite(e.cp));
    const sum=f=>passes.reduce((n,e)=>n+f(e),0);
    const gain=e=>e.ry-e.ty,flight=e=>Math.hypot(e.rx-e.tx,gain(e));
    const huck=e=>gain(e)>30&&flight(e)>40;
    const nonHucks=passes.filter(e=>!huck(e));
    assert.equal(p.throws,passes.length,p.name);
    assert.equal(p.games,new Set(events.map(e=>e.game)).size,p.name);
    assert.deepEqual([...new Set(events.map(e=>e.team))],[p.team]);
    assert.equal(p.completions,sum(e=>Number(e.complete)));
    assert.equal(p.drops,sum(e=>Number(e.drop)));
    assert.equal(p.huckAttempts,sum(e=>Number(huck(e))));
    close(p.meanGain,sum(gain)/passes.length,p.name+' gain');
    close(p.meanFlight,sum(flight)/passes.length,p.name+' flight');
    close(p.nonHuckMeanGain,nonHucks.reduce((n,e)=>n+gain(e),0)/nonHucks.length,p.name+' non-huck gain');
    close(p.shortShare,sum(e=>Number(flight(e)<=10))/passes.length,p.name+' short');
    close(p.forwardShare,sum(e=>Number(gain(e)>Math.abs(e.rx-e.tx)))/passes.length,p.name+' forward');
    close(p.lateralShare,sum(e=>Number(Math.abs(gain(e))<=Math.abs(e.rx-e.tx)))/passes.length,p.name+' lateral');
    close(p.throwingY,sum(e=>e.ty)/passes.length,p.name+' throwing Y');
    close(p.completionRate,p.completions/p.throws,p.name+' completion');
    assert.equal(p.scoredPasses,scored.length);
    close(p.xcp,scored.reduce((n,e)=>n+e.cp,0)/scored.length,p.name+' xCP');
    close(p.sourceCpoe,(p.completions+p.drops)/p.throws-p.xcp,p.name+' CPOE');
    close(p.throwerAec,events.reduce((n,e)=>n+(e.throwAec??0),0),p.name+' aEC');
  }
});

test('search covers non-example players, accents and teams; team scope and empty states work',()=>{
  assert.equal(throwerDirectory(profiles,{search:'spencer lofink'})[0].name,'Spencer Lofink');
  assert.equal(throwerDirectory(profiles,{search:'  de marree  '})[0].name,'Daan De Marrée');
  assert.ok(throwerDirectory(profiles,{search:'Seattle'}).every(p=>p.team==='cascades'));
  assert.ok(throwerDirectory(profiles,{team:'hustle'}).every(p=>p.team==='hustle'));
  assert.deepEqual(throwerDirectory(profiles,{team:'glory',search:'Spencer Lofink'}),[]);
  assert.equal(throwerDirectory(profiles)[0].name,'Austin Taylor');
  assert.equal(throwerDirectory(profiles,{sort:'throws'}).length,profiles.length);
});

test('medians remain league-wide and profile descriptions do not depend on outcomes',()=>{
  for(const r of reference){
    const values=profiles.map(p=>p[r.feature]).filter(Number.isFinite).sort((a,b)=>a-b);
    const mid=Math.floor(values.length/2),expected=values.length%2?values[mid]:(values[mid-1]+values[mid])/2;
    close(r.median,expected,r.feature+' median');
  }
  const a=profiles.find(p=>p.id==='ataylor'),b=profiles.find(p=>p.name==='Spencer Lofink');
  assert.ok(a&&b);
  const before=throwerComparison(a,null,reference,PASSING_TRAITS);
  throwerDirectory(profiles,{team:'hustle',search:'Austin'});
  assert.deepEqual(throwerComparison(a,null,reference,PASSING_TRAITS),before);
  assert.deepEqual(observedThrowingTraits(a,reference),observedThrowingTraits({...a,throws:10000,completionRate:0,sourceCpoe:-1,throwerAec:-1000,assists:0},reference));
  const compared=throwerComparison(a,b,reference,PASSING_TRAITS);
  assert.ok(compared.every(r=>r.comparisonValue===b[r.field]));
  assert.deepEqual(throwerComparison(null,b,reference,PASSING_TRAITS),[]);
  assert.deepEqual(observedThrowingTraits({...a,shortSharePercentile:null,lateralSharePercentile:null,meanGainPercentile:null,throwingYPercentile:null,sidelineSharePercentile:null},reference),[]);
});
