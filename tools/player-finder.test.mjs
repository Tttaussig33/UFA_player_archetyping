import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {angleDifference,distanceAngleLeague,findPlayers,finderEvidence,indexPlayerThrows,validMinimumThrows} from '../src/content/dashboard/player-finder-model.js';

const data=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=data.queries.events.rows,players=data.queries.shownSpaceThrowers.rows;
const index=indexPlayerThrows(events),league=distanceAngleLeague(index,players,15,20);
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-9,`${actual} != ${expected}`);
const player=(id,team='one')=>({id,name:id,team,teamName:team});
const pass=(id,thrower,angle=0,distance=16,extra={})=>({id,thrower,tx:0,ty:0,rx:-Math.sin(angle*Math.PI/180)*distance,ry:Math.cos(angle*Math.PI/180)*distance,throwAngle:angle,complete:true,...extra});

test('angle separation takes the short path across zero and backward',()=>{
  close(angleDifference(359,1),2);close(angleDifference(-179,179),2);
  close(angleDifference(90,-90),180);close(angleDifference(720,0),0);
  assert.equal(angleDifference(null,0),null);assert.equal(angleDifference(0,NaN),null);
});

test('similar-arrow groups honor tolerance inclusively, minimum count, and candidate team without changing the reference',()=>{
  const rows=[pass('a','reference',179),pass('b','close',-179),pass('c','far',160),pass('d','undefined',90),pass('e','undefined',-90),pass('stall','close',0,16,{stall:true})];
  const people=[player('reference'),player('close','two'),player('far','two'),player('undefined','two')];
  const sample=distanceAngleLeague(indexPlayerThrows(rows),people,15,20);
  const result=findPlayers(sample,{referenceId:'reference',minimum:1,tolerance:2,team:'two'});
  assert.deepEqual(result.rows.map(row=>row.id),['close']);
  close(result.referenceAngle,179);close(result.rows[0].angleDifference,2);
  assert.equal(findPlayers(sample,{referenceId:'reference',minimum:2,tolerance:180}).rows.length,0);
  assert.equal(findPlayers(sample,{referenceId:'undefined',minimum:1,tolerance:180}).rows.length,0);
  assert.deepEqual(findPlayers(sample,{referenceId:'reference',minimum:1,tolerance:180,team:'all'}).rows.map(row=>row.id),['close','far']);
});

test('direction and distance intersect; rates use attempts, and all directions restores stationary/missing-angle passes',()=>{
  const rows=[pass('lower','p',30,15),pass('inside','p',40,17,{complete:false,drop:true}),pass('upper-angle','p',60,17),pass('upper-distance','p',0,20),
    pass('zero','p',0,0),pass('no-angle','p',null,17),pass('missing-coordinates','p',40,17,{tx:null}),pass('stall','p',30,17,{stall:true})];
  const indexed=indexPlayerThrows(rows),people=[player('p')];
  const sample=distanceAngleLeague(indexed,people,15,20);
  const result=findPlayers(sample,{mode:'throws',direction:'1',minimum:1}).rows[0];
  assert.equal(result.attempts,2);assert.equal(result.completed,1);close(result.completion,.5);close(result.share,2/7);
  const all=distanceAngleLeague(indexed,people,0,100);
  assert.equal(findPlayers(all,{mode:'throws',direction:'all',minimum:1}).rows[0].attempts,6);
  assert.equal(findPlayers(sample,{mode:'throws',direction:'1',minimum:3}).rows.length,0);
});

test('volume, frequency, and completion orderings answer different questions without changing the matching rows',()=>{
  const source=[pass('a1','a',40),pass('a2','a',40,16,{complete:false}),pass('a3','a',40),...Array.from({length:7},(_,i)=>pass(`a${i+4}`,'a',100)),pass('b1','b',40),pass('b2','b',40)];
  const sample=distanceAngleLeague(indexPlayerThrows(source),[player('a'),player('b')],15,20);
  for(const [sort,expected] of [['attempts',['a','b']],['share',['b','a']],['completion',['b','a']]]){
    const rows=findPlayers(sample,{mode:'throws',direction:'1',minimum:1,sort}).rows;
    assert.deepEqual(rows.map(row=>row.id),expected);
    assert.deepEqual(rows.map(row=>row.attempts).sort(),[2,3]);
  }
});

test('invalid minimums and directions return an explicit invalid state',()=>{
  for(const minimum of ['',0,-1,1.2,'abc',Infinity]){
    assert.equal(validMinimumThrows(minimum),false);
    assert.equal(findPlayers(league,{referenceId:'aatkins',minimum}).valid,false);
  }
  assert.equal(validMinimumThrows('1'),true);
  assert.equal(findPlayers(league,{mode:'throws',direction:'12',minimum:1}).valid,false);
  assert.equal(findPlayers(league,{referenceId:'aatkins',minimum:1,tolerance:181}).valid,false);
});

test('default results agree with independent Python calculations and retain the named comparison players',()=>{
  const found=findPlayers(league,{referenceId:'aatkins'});
  assert.equal(found.rows.length,160);
  assert.deepEqual(found.rows.slice(0,5).map(row=>row.id),['jcowan','aroy','jthornton','mdillard','kkoo']);
  close(found.rows[0].averageAngle,2.612474905229845);close(found.rows[0].angleDifference,.07271305902679615);
  assert.equal(found.rows[0].attempts,59);close(found.rows[0].averageDistance,17.25319194906266);
  assert.equal(found.rows.find(row=>row.id==='jnissen').attempts,150);
  assert.ok(!found.rows.some(row=>row.id==='aatkins'));
  assert.equal(findPlayers(league,{referenceId:'aatkins',minimum:10000}).rows.length,0);
});

test('joint direction results agree with independent attempt, completion, and frequency counts',()=>{
  const rows=findPlayers(league,{mode:'throws',direction:'1',minimum:5,sort:'attempts'}).rows;
  assert.equal(rows.length,153);
  assert.deepEqual(rows.slice(0,5).map(row=>[row.id,row.attempts,row.completed]),[['aroy',32,31],['glarson',27,26],['jlouie',26,26],['jnissen',25,24],['myorgason',25,24]]);
  close(rows[0].share,32/522);close(rows[0].completion,31/32);
  const longer=distanceAngleLeague(index,players,40,110);
  const deep=findPlayers(longer,{mode:'throws',direction:'0',minimum:5,sort:'attempts'}).rows;
  assert.equal(deep.length,143);assert.equal(deep[0].id,'jfelton');assert.equal(deep[0].attempts,41);assert.equal(deep[0].completed,24);
});

test('every selected count and rate reconciles independently for every direction and team',()=>{
  for(const direction of ['all',...Array.from({length:12},(_,i)=>String(i))]){
    const rows=findPlayers(league,{mode:'throws',direction,minimum:1}).rows;
    for(const row of rows){
      const all=index.get(row.id);
      const selected=all.filter(e=>[e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)&&
        (e.rx-e.tx)**2+(e.ry-e.ty)**2>=225&&(e.rx-e.tx)**2+(e.ry-e.ty)**2<400&&
        (direction==='all'||Number.isFinite(e.throwAngle)&&Math.floor(((e.throwAngle%360)+360)%360/30)===Number(direction)));
      assert.equal(row.attempts,selected.length,row.name);
      assert.equal(row.completed,selected.filter(e=>e.complete).length,row.name);
      close(row.share,selected.length/all.length);
    }
    for(const team of new Set(players.map(p=>p.team))){
      const filtered=findPlayers(league,{mode:'throws',direction,minimum:1,team}).rows;
      assert.deepEqual(filtered.map(row=>row.id),rows.filter(row=>row.team===team).map(row=>row.id));
    }
  }
});

test('evidence retains candidate denominators and the reference exactly once, without unrelated players',()=>{
  const rows=findPlayers(league,{referenceId:'aatkins',team:'breeze'}).rows;
  assert.ok(rows.length>0);
  const evidence=finderEvidence(league,rows,'aatkins'),included=new Set([...rows.map(row=>row.id),'aatkins']);
  assert.ok(evidence.every(e=>included.has(e.thrower)&&!e.stall));
  assert.equal(new Set(evidence.map(e=>e.id)).size,evidence.length);
  for(const id of included)assert.equal(evidence.filter(e=>e.thrower===id).length,index.get(id).length);
  assert.deepEqual(finderEvidence(league,[],null),[]);
});
