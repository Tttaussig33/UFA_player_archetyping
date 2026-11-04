import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {averageAngleLabel,circularMean,distanceAngleModel,directionDisplayRows,directionScale,validDistanceRange} from '../src/content/dashboard/distance-angle-model.js';

const data=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=data.queries.events.rows,players=data.queries.shownSpaceThrowers.rows;
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-9,`${actual} != ${expected}`);
const pass=(id,distance,angle=0,extra={})=>({id,thrower:'p',tx:0,ty:0,rx:-Math.sin(angle*Math.PI/180)*distance,ry:Math.cos(angle*Math.PI/180)*distance,throwAngle:angle,complete:true,...extra});

test('mean angles wrap around forward and backward and leave cancellation undefined',()=>{
  close(circularMean([359,1]),0);
  close(Math.abs(circularMean([170,-170])),180);
  close(circularMean([0,90]),45);
  assert.equal(circularMean([90,-90]),null);
  assert.equal(circularMean([]),null);
  assert.equal(circularMean([null,undefined,NaN,Infinity]),null);
  close(circularMean([-30,null,undefined]),-30);
  assert.equal(averageAngleLabel(359),'1.0° right of forward');
  assert.equal(averageAngleLabel(180),'180° backward');
  assert.equal(averageAngleLabel(-.01),'0° straight forward');
  assert.equal(averageAngleLabel(null),'No single average');
});

test('distance bands include the lower edge and exclude the upper edge without dropping turnovers',()=>{
  const source=[pass('below',14.99),pass('lower',15),pass('drop',17,0,{complete:false,drop:true,receiver:null}),
    pass('inside',19.99),pass('upper',20),pass('missing',16,0,{rx:null}),
    pass('stall',18,0,{stall:true}),pass('other',18,0,{thrower:'q'})];
  const model=distanceAngleModel(source,'p',15,20);
  assert.deepEqual(model.rows.map(e=>e.id),['lower','drop','inside']);
  assert.equal(model.allPasses.length,6);
  assert.equal(model.missingLocations,1);
  assert.equal(model.share,.5);
  assert.equal(model.groups[0].completed,2);
  close(model.averageDistance,(15+17+19.99)/3);
});

test('zero distance remains in the distance mean; only usable positive-distance directions enter the angle mean',()=>{
  const model=distanceAngleModel([pass('short',10,0),pass('long',90,90),pass('zero',0,180),pass('no-angle',20,null)],'p');
  assert.equal(model.count,4);
  assert.equal(model.directional.length,2);
  assert.equal(model.missingDirections,2);
  close(model.averageDistance,30);
  close(model.averageAngle,45); // Equal votes, not length-weighted vectors.
  assert.equal(model.groups[0].share,.5);
  assert.equal(model.groups[3].share,.5);
  assert.deepEqual(model.leaders.map(g=>g.id),['0','3']);
});

test('signed angles and all 30-degree boundaries enter exactly one direction bin',()=>{
  const source=Array.from({length:12},(_,i)=>pass(String(i),15,i<6?i*30:i*30-360));
  const model=distanceAngleModel(source,'p');
  assert.deepEqual(model.groups.map(g=>g.count),Array(12).fill(1));
  assert.equal(model.leaders.length,12);
  assert.equal(model.averageAngle,null);
  const nearForward=distanceAngleModel([pass('left',15,0),pass('right',15,-.1)],'p');
  assert.equal(nearForward.groups[0].count,1);
  assert.equal(nearForward.groups[11].count,1);
  assert.equal(nearForward.groups[11].label,'0–30° right');
});

test('empty ranges and absent players do not fabricate averages, rates, or a winning direction',()=>{
  const empty=distanceAngleModel([pass('short',10)],'p',15,20);
  assert.equal(empty.count,0);assert.equal(empty.share,0);
  assert.equal(empty.averageDistance,null);assert.equal(empty.averageAngle,null);
  assert.deepEqual(empty.leaders,[]);
  assert.ok(empty.groups.every(g=>g.count===0&&g.share===null));
  assert.equal(distanceAngleModel([],'absent').share,null);
  assert.equal(directionScale([empty]),.05);
});

test('range validation rejects incomplete, negative, nonnumeric, and reversed input',()=>{
  for(const [lower,upper] of [['','20'],['15',''],['-1','20'],['20','15'],['20','20'],['abc','20'],['15','Infinity']])assert.equal(validDistanceRange(lower,upper),false);
  assert.equal(validDistanceRange('14.5','15.5'),true);
  assert.equal(validDistanceRange('0','110'),true);
});

test('Atkins and Nissen match independently calculated selected-range and whole-season results',()=>{
  const fixtures=[
    ['aatkins',137,17.26949108511166,2.685187964256631,[24,24,16,7,0,0,0,4,3,15,20,24],551,21.34710229308869,7.592580378515296],
    ['jnissen',150,17.329979870173528,6.5131759218791485,[17,25,21,12,3,1,1,1,6,18,27,18],446,18.977550671559122,4.6189027558388025],
  ];
  for(const [id,n,d,a,bins,total,allD,allA] of fixtures){
    const band=distanceAngleModel(events,id,15,20),all=distanceAngleModel(events,id);
    assert.equal(band.count,n);close(band.averageDistance,d);close(band.averageAngle,a);
    assert.deepEqual(band.groups.map(g=>g.count),bins);
    assert.equal(all.count,total);close(all.averageDistance,allD);close(all.averageAngle,allA);
    close(band.share,n/total);
  }
});

test('every player reconciles selected records, frequency denominators, and inspectable display rows',()=>{
  for(const player of players){
    const passes=events.filter(e=>e.thrower===player.id&&!e.stall);
    const model=distanceAngleModel(passes,player.id,15,20);
    const expected=passes.filter(e=>[e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)&&
      (e.rx-e.tx)**2+(e.ry-e.ty)**2>=225&&(e.rx-e.tx)**2+(e.ry-e.ty)**2<400);
    assert.deepEqual(model.rows.map(e=>e.id),expected.map(e=>e.id),player.name);
    assert.equal(model.allPasses.length,player.recordedAttempts,player.name);
    assert.equal(model.groups.reduce((s,g)=>s+g.count,0),model.directional.length,player.name);
    const displayed=directionDisplayRows(model,player);
    assert.equal(displayed.length,12);
    assert.ok(displayed.every(g=>g.playerId===player.id&&g.selectedAttempts===model.count&&!('rows' in g)));
  }
});

test('source angles agree with the plotted field orientation for every positive-distance non-stall throw',()=>{
  let checked=0;
  for(const e of events){
    if(e.stall||![e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)||Math.hypot(e.rx-e.tx,e.ry-e.ty)===0)continue;
    assert.ok(Number.isFinite(e.throwAngle),e.id);
    const geometric=Math.atan2(e.tx-e.rx,e.ry-e.ty)*180/Math.PI;
    const error=((e.throwAngle-geometric+180)%360+360)%360-180;
    assert.ok(Math.abs(error)<1e-6,e.id);
    checked++;
  }
  assert.equal(checked,77822);
});
