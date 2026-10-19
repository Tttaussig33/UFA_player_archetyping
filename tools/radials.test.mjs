import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildRadials,directionAngle,radialRecords,radialPoint,radialWedge} from '../src/content/dashboard/radial-model.js';
const snapshot=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=snapshot.queries.events.rows;
const fixture=JSON.parse(fs.readFileSync(new URL('../data/database-metadata/2026-10-12/alex-atkins-2026-radial.json',import.meta.url)));

test('Atkins 2026 reproduces every bucket and both totals returned by the database function',()=>{
  const model=buildRadials(events,'aatkins');
  assert.equal(model.throw.total,fixture.totalThrowsAsThrower);
  assert.equal(model.receive.total,fixture.totalThrowsAsReceiver);
  assert.deepEqual(model.throw.buckets.map(bucket=>bucket.count),fixture.buckets.map(bucket=>bucket.throwerCount));
  assert.deepEqual(model.receive.buckets.map(bucket=>bucket.count),fixture.buckets.map(bucket=>bucket.receiverCount));
  assert.deepEqual(model.throw.buckets.map(bucket=>bucket.centerAngle),fixture.buckets.map(bucket=>bucket.centerAngle));
  assert.equal(model.throw.total,552);assert.equal(model.receive.total,469);
});

test('direction boundaries wrap at 360 and retain missing angles as unknown',()=>{
  const angles=[0,29.9999,30,359.9999,360,-1,-360,720,null,undefined,NaN];
  const rows=angles.map((throwAngle,i)=>({id:String(i),thrower:'a',receiver:'b',throwAngle}));
  const model=buildRadials(rows,'a');
  assert.deepEqual(model.throw.buckets.map(bucket=>bucket.count),[5,1,0,0,0,0,0,0,0,0,0,2]);
  assert.equal(model.throw.missingAngle,3);assert.equal(model.throw.total,8);
  assert.equal(directionAngle(null),null);assert.equal(directionAngle(-1),359);
  assert.equal(buildRadials(rows,'a',{bucketCount:2}).bucketCount,4);
  assert.equal(buildRadials(rows,'a',{bucketCount:99}).bucketCount,36);
  assert.equal(buildRadials(rows,'a',{bucketCount:8}).throw.total,8);
});

test('all recorded includes stalls and drops; completed and huck scopes have their own denominators',()=>{
  const rows=[
    {id:'a',thrower:'a',receiver:'b',throwAngle:0,complete:true,tx:0,ty:0,rx:0,ry:40},
    {id:'b',thrower:'a',receiver:'b',throwAngle:30,drop:true,tx:0,ty:0,rx:0,ry:40},
    {id:'c',thrower:'a',receiver:null,throwAngle:60,stall:true,tx:0,ty:0,rx:0,ry:40},
    {id:'d',thrower:'b',receiver:'a',throwAngle:90,complete:true,tx:0,ty:0,rx:0,ry:20},
    {id:'e',thrower:'a',receiver:null,throwAngle:120,tx:0,ty:0,rx:40,ry:0},
    {id:'f',thrower:'b',receiver:'a',throwAngle:300,tx:null,ty:0,rx:0,ry:50},
  ];
  const all=buildRadials(rows,'a'),completed=buildRadials(rows,'a',{outcome:'complete'}),hucks=buildRadials(rows,'a',{passType:'hucks'});
  assert.equal(all.throw.total,4);assert.equal(all.receive.total,2);
  assert.equal(all.receive.buckets[3].count,1); // Incoming angle is not rotated.
  assert.equal(completed.throw.total,1);assert.equal(completed.receive.total,1);
  assert.equal(hucks.throw.total,2);assert.equal(hucks.receive.total,0);
  assert.deepEqual(hucks.sourceRows.map(row=>row.id),['a','b']);
  assert.equal(hucks.throw.buckets[0].share,.5);
  assert.deepEqual(radialRecords(hucks,{role:'throw',index:1}).map(row=>row.id),['b']);
  assert.deepEqual(radialRecords(all,null),rows);
});

test('all teams and phases reconcile counts, shares and original event IDs',()=>{
  for(const team of snapshot.queries.teams.rows)for(const phase of ['Regular season','Playoffs']) {
    const scope=events.filter(event=>event.team===team.id&&event.phase===phase);
    const player=scope.find(event=>event.thrower&&event.thrower!=='unknown')?.thrower;
    const model=buildRadials(scope,player);
    for(const [role,endpoint] of [['throw','thrower'],['receive','receiver']]) {
      const expected=player?scope.filter(event=>event[endpoint]===player&&Number.isFinite(event.throwAngle)):[];
      const side=model[role];
      assert.equal(side.total,expected.length,`${team.id}/${phase}/${role}`);
      assert.equal(side.buckets.reduce((sum,bucket)=>sum+bucket.count,0),expected.length);
      assert.deepEqual(new Set(side.buckets.flatMap(bucket=>bucket.events.map(event=>event.id))),new Set(expected.map(event=>event.id)));
      if(side.total)assert.ok(Math.abs(side.buckets.reduce((sum,bucket)=>sum+bucket.share,0)-1)<1e-12);
      else assert.ok(side.buckets.every(bucket=>bucket.share===null));
    }
  }
});

test('huck completions reconcile to the known full-season and regular-season connection totals',()=>{
  assert.equal(buildRadials(events,'aatkins',{passType:'hucks',outcome:'complete'}).throw.total,45);
  assert.equal(buildRadials(events.filter(event=>event.phase==='Regular season'),'aatkins',{passType:'hucks',outcome:'complete'}).throw.total,28);
  assert.equal(buildRadials(events,'aatkins',{passType:'hucks'}).throw.total,53);
  assert.equal(buildRadials(events,'missing-player').sourceRows.length,0);
  assert.equal(buildRadials(events,'unknown').sourceRows.length,0);
});

test('display geometry retains the reference direction convention and produces finite paths',()=>{
  assert.deepEqual(radialPoint(0,60,76),[76,16]);
  assert.deepEqual(radialPoint(90,60,76),[136,76]);
  assert.ok(radialPoint(330,60,76)[0]<76);
  for(const angle of [0,30,180,330])assert.ok(!/NaN|Infinity/.test(radialWedge(angle,30,144)));
});
