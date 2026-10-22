import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {passGeometry,buildConnections,connectionPlayerDirectory,connectionPlayers,connectionSearchTeam,selectedConnectionEvents} from '../src/content/dashboard/connections-model.js';
const snapshot=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=snapshot.queries.events.rows;
const pass=(id,thrower,receiver,more={})=>({id,thrower,receiver,tx:0,ty:20,rx:0,ry:70,complete:true,stall:false,...more});

test('player search includes the full reviewed roster and selects a compatible team without dropping transfers',()=>{
 const players={a:{name:'Alex'},b:{name:'Ben'},c:{name:'Casey'},d:{name:'Daan De Marrée'}};
 const rows=[pass('one','a','b',{team:'east'}),pass('two','b','d',{team:'west'})];
 const directory=connectionPlayerDirectory(rows,players,[{id:'east',name:'East Team'},{id:'west',name:'West Team'}]);
 assert.equal(directory.length,4,'A named player remains searchable even without passes in the selected scope');
 const alex=directory.find(p=>p.id==='a'),ben=directory.find(p=>p.id==='b');
 assert.equal(alex.label,'Alex · East Team');
 assert.equal(connectionSearchTeam(alex,'west'),'east');
 assert.equal(connectionSearchTeam(alex,'all'),'all');
 assert.equal(connectionSearchTeam(ben,'west'),'west');
 assert.equal(connectionSearchTeam(ben,'other'),'all','Players recorded on multiple teams keep all their records');
 assert.equal(connectionSearchTeam(directory.find(p=>p.id==='c'),'east'),'all');
});

test('hucks strictly exceed both cutoffs, exclude stalls, and reject missing coordinates',()=>{
 assert.equal(passGeometry(pass('distance-edge','a','b',{rx:0,ry:60})).huck,false);
 assert.equal(passGeometry(pass('gain-edge','a','b',{rx:30,ry:50})).huck,false);
 assert.equal(passGeometry(pass('just-longer','a','b',{rx:0,ry:60.01})).huck,true);
 assert.equal(passGeometry(pass('just-forward','a','b',{rx:30,ry:50.01})).huck,true);
 assert.equal(passGeometry(pass('short','a','b',{ry:59.99})).huck,false);
 assert.equal(passGeometry(pass('sideways','a','b',{rx:50,ry:30})).huck,false);
 assert.equal(passGeometry(pass('backward','a','b',{ry:-30})).huck,false);
 assert.equal(passGeometry(pass('stall','a','b',{stall:true})).huck,false);
 assert.deepEqual(passGeometry(pass('missing','a','b',{rx:null})),{distance:null,gain:null,huck:false});
});

test('incoming and outgoing are independent passes, and unknown targets are retained in attempts',()=>{
 const rows=[pass('incoming','b','a'),pass('outgoing','a','c'),pass('drop','a','d',{complete:false,drop:true}),pass('away','a',null,{complete:false}),pass('stall','a',null,{complete:false,stall:true})];
 const completed=buildConnections(rows,'a');
 assert.equal(completed.incoming.total,1);assert.equal(completed.outgoing.total,1);
 assert.equal(completed.sourceRows.length,2);
 const attempted=buildConnections(rows,'a',{outcome:'all'});
 assert.equal(attempted.incoming.total,1);assert.equal(attempted.outgoing.total,3);
 assert.equal(attempted.outgoing.all.find(g=>g.partnerId==='unknown').count,1);
 assert.equal(attempted.sourceRows.length,4);
 assert.ok(attempted.chartRows.every(r=>r.passer===null||r.receiver===null),'No invented three-player sequences');
});

test('top partners plus Other conserve counts and selected links retrieve only their original records',()=>{
 const rows=Array.from({length:10},(_,i)=>pass(`p${i}`,'a',`b${i%4}`));
 rows.push(pass('in','z','a'));
 const model=buildConnections(rows,'a',{limit:2});
 assert.equal(model.outgoing.total,10);
 assert.equal(model.outgoing.displayed.reduce((n,g)=>n+g.count,0),10);
 const other=model.outgoing.displayed.find(g=>g.partnerId==='other');
 assert.equal(other.count,4);
 const selected=selectedConnectionEvents(model,[{field:'player',name:'a'},{field:'receiver',name:other.partner}]);
 assert.equal(selected.length,4);assert.ok(selected.every(e=>['b2','b3'].includes(e.receiver)));
 assert.deepEqual(selectedConnectionEvents(model,[]),rows);
 assert.equal(buildConnections(rows,'a',{limit:Infinity}).outgoing.displayed.length,4);
});

test('Alex Atkins regular-season hucks reconcile to the independently reviewed 35 attempts and 28 completions',()=>{
 const regular=events.filter(e=>e.phase==='Regular season'&&e.team==='empire');
 const completed=buildConnections(regular,'aatkins',{passType:'hucks'});
 const attempts=buildConnections(regular,'aatkins',{passType:'hucks',outcome:'all'});
 assert.equal(completed.outgoing.total,28);assert.equal(attempts.outgoing.total,35);
 assert.equal(completed.incoming.total,9);
 assert.equal(completed.outgoing.all.find(g=>g.partnerId==='bjagt').count,6);
 assert.equal(attempts.outgoing.all.find(g=>g.partnerId==='unknown').count,5);
 const all=buildConnections(regular,'aatkins');
 assert.equal(all.incoming.total,364);assert.equal(all.outgoing.total,419);
});

test('all 22 teams and both phases preserve each eligible pass once per relevant direction',()=>{
 for(const team of snapshot.queries.teams.rows)for(const phase of ['Regular season','Playoffs']) {
  const scoped=events.filter(e=>e.team===team.id&&e.phase===phase);
  const id=connectionPlayers(scoped)[0];if(!id)continue;
  for(const passType of ['all','hucks'])for(const outcome of ['all','complete']) {
   const expected=scoped.filter(e=>!e.stall&&(e.thrower===id||e.receiver===id)&&(outcome==='all'||e.complete)&&(passType==='all'||passGeometry(e).huck));
   const model=buildConnections(scoped,id,{passType,outcome,limit:5});
   assert.deepEqual(model.sourceRows,expected);
   assert.equal(new Set(model.sourceRows.map(e=>e.id)).size,model.sourceRows.length);
   assert.equal(model.incoming.total,expected.filter(e=>e.receiver===id).length);
   assert.equal(model.outgoing.total,expected.filter(e=>e.thrower===id).length);
   for(const side of ['incoming','outgoing'])assert.equal(model[side].displayed.reduce((n,g)=>n+g.count,0),model[side].total);
  }
 }
});

test('empty and one-sided scopes create no phantom links',()=>{
 const empty=buildConnections([],'a',{passType:'hucks'});
 assert.deepEqual(empty.chartRows,[]);assert.deepEqual(empty.sourceRows,[]);
 const outbound=buildConnections([pass('out','a','b')],'a');
 assert.equal(outbound.incoming.total,0);assert.equal(outbound.outgoing.total,1);
 assert.equal(outbound.chartRows.length,1);assert.equal(outbound.chartRows[0].passer,null);
});
