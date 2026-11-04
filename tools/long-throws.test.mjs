import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {longThrowsModel,longThrowRecords,fieldPoint,throwHitArea,LONG_FIELD} from '../src/content/dashboard/long-throws-model.js';

const data=JSON.parse(fs.readFileSync(new URL('../src/data.json',import.meta.url)));
const events=data.queries.events.rows,players=data.queries.shownSpaceThrowers.rows;
const pass=(id,rx,ry,extra={})=>({id,thrower:'p',tx:0,ty:0,rx,ry,complete:true,...extra});

test('distance bands have no gaps or double counts at 0, 10, 20, 30 and 40 yards',()=>{
  const rows=[pass('zero',0,0),pass('below-ten',0,9.999),pass('ten',0,10),pass('nineteen',0,-19),
    pass('twenty',20,0,{complete:false,drop:true}),pass('thirty',0,30),pass('forty',0,40),
    pass('stall',0,8,{stall:true}),pass('missing',null,8)];
  const expected={under10:['zero','below-ten'],'10to20':['ten','nineteen'],'20to30':['twenty'],'30to40':['thirty'],long:['forty']};
  for(const [type,ids] of Object.entries(expected)){
    const model=longThrowsModel(rows,'p',type);
    assert.deepEqual(model.rows.map(e=>e.id),ids);
    assert.equal(model.allPasses.length,8);
    assert.equal(model.share,ids.length/8);
    assert.equal(model.missingLocations,1);
  }
  assert.equal(longThrowsModel(rows,'p','20to30').completion,0);
  const hit=throwHitArea(rows[0]);
  assert.ok(!hit.includes('NaN')&&!hit.includes('Infinity'));
  assert.equal(new Set(hit.slice(8,-1).split(',')).size,4,'zero-distance dots remain selectable');
});

test('40+ includes its boundary; hucks require both strict thresholds and forward motion',()=>{
  const rows=[pass('forty',0,40),pass('thirty-forward',40,30),pass('huck',1,41),
    pass('long-swing',45,0),pass('backward',0,-45),pass('short',0,39.99),
    pass('stall',0,90,{stall:true}),pass('missing',null,90),pass('other-player',0,50,{thrower:'q'})];
  const long=longThrowsModel(rows,'p'),huck=longThrowsModel(rows,'p','hucks');
  assert.deepEqual(long.rows.map(e=>e.id),['forty','thirty-forward','huck','long-swing','backward']);
  assert.deepEqual(huck.rows.map(e=>e.id),['huck']);
  assert.equal(long.allPasses.length,7);
  assert.equal(long.missingLocations,1);
  assert.equal(long.share,5/7);
});

test('incomplete throws, drops and unnamed targets stay in attempts; zero has no rate',()=>{
  const rows=[pass('complete',0,50),pass('drop',0,50,{complete:false,drop:true}),pass('unnamed',0,50,{complete:false,receiver:null})];
  const model=longThrowsModel(rows,'p');
  assert.equal(model.attempts,3);
  assert.equal(model.completed,1);
  assert.equal(model.completion,1/3);
  assert.equal(longThrowRecords(model,{name:'P',teamName:'Team'},{}).at(-1).receiver,'Unrecorded target');
  const empty=longThrowsModel([pass('short',0,10)],'p');
  assert.equal(empty.attempts,0);
  assert.equal(empty.completion,null);
  assert.equal(empty.share,0);
  assert.equal(longThrowsModel([],'missing').share,null);
});

test('Atkins and Nissen match independent endpoint counts for the full recorded season',()=>{
  for(const [id,total,attempts,completed,hucks,huckCompletions] of [['aatkins',551,58,49,53,45],['jnissen',446,22,16,20,15]]){
    const long=longThrowsModel(events,id),huck=longThrowsModel(events,id,'hucks');
    assert.equal(long.allPasses.length,total);
    assert.equal(long.attempts,attempts);
    assert.equal(long.completed,completed);
    assert.equal(long.completion,completed/attempts);
    assert.equal(long.share,attempts/total);
    assert.equal(huck.attempts,hucks);
    assert.equal(huck.completed,huckCompletions);
  }
});

test('all 747 players reconcile fields, records and all six filters; distance bands partition their located attempts',()=>{
  for(const p of players){
    const passes=events.filter(e=>e.thrower===p.id&&!e.stall);
    const bands={under10:[0,100],'10to20':[100,400],'20to30':[400,900],'30to40':[900,1600],long:[1600,Infinity]};
    let distanceTotal=0;
    for(const type of [...Object.keys(bands),'hucks']){
      const model=longThrowsModel(passes,p.id,type);
      const expected=passes.filter(e=>[e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)&&
        (type==='hucks'?(e.rx-e.tx)**2+(e.ry-e.ty)**2>1600&&e.ry-e.ty>30:
          (e.rx-e.tx)**2+(e.ry-e.ty)**2>=bands[type][0]&&(e.rx-e.tx)**2+(e.ry-e.ty)**2<bands[type][1]));
      assert.deepEqual(model.rows.map(e=>e.id),expected.map(e=>e.id),p.name);
      assert.equal(new Set(model.rows.map(e=>e.id)).size,model.attempts,p.name);
      assert.equal(longThrowRecords(model,p,{}).length,model.attempts,p.name);
      assert.equal(model.completed,expected.filter(e=>e.complete).length,p.name);
      assert.equal(model.allPasses.length,p.recordedAttempts,p.name);
      if(type!=='hucks')distanceTotal+=model.attempts;
    }
    assert.equal(distanceTotal,passes.filter(e=>[e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)).length,p.name);
  }
});

test('both fields keep physical yard distances and attacking orientation',()=>{
  const [x0,y0]=fieldPoint(-26.65,0),[x1,y1]=fieldPoint(26.65,120);
  assert.equal(x0,LONG_FIELD.left);assert.equal(y0,LONG_FIELD.top);
  assert.ok(Math.abs(x1-x0-120*LONG_FIELD.scale)<1e-9);
  assert.ok(Math.abs(y1-y0-53.3*LONG_FIELD.scale)<1e-9);
  assert.ok(fieldPoint(0,80)[0]>fieldPoint(0,20)[0]);
  assert.equal(fieldPoint(0,80)[1],fieldPoint(0,20)[1]);
});
