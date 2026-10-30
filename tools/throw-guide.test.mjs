import test from 'node:test';
import assert from 'node:assert/strict';
import {guideMetrics,guideEndpoint,maxGuideFlight,clampGuidePoint,THROW_EXAMPLES} from '../src/content/dashboard/throw-guide-model.js';

test('field guide distinguishes forward progress from flight distance',()=>{
  const m=guideMetrics({tx:-15,ty:40,rx:15,ry:80});
  assert.equal(m.gain,40);assert.equal(m.lateral,30);assert.equal(m.distance,50);
  assert.equal(m.category,'forward');assert.equal(m.huck,true);
  const backward=guideMetrics({tx:-15,ty:80,rx:15,ry:40});
  assert.equal(backward.gain,-40);assert.equal(backward.distance,50);
  assert.equal(backward.category,'backward');assert.equal(backward.huck,false);
});

test('45° examples agree with the strict Player styles direction boundaries',()=>{
  assert.deepEqual(THROW_EXAMPLES.map(p=>guideMetrics(p).category),['forward','sideways','sideways','sideways','backward','forward']);
  const start={x:-15,y:60};
  for(const [angle,category] of [[0,'forward'],[44.999,'forward'],[45,'sideways'],[-45,'sideways'],[90,'sideways'],[135,'sideways'],[-135,'sideways'],[135.001,'backward'],[180,'backward']]){
    const end=guideEndpoint(start,angle,20);
    assert.equal(guideMetrics({tx:start.x,ty:start.y,rx:end.x,ry:end.y}).category,category,`${angle}°`);
  }
  const zero=guideMetrics({tx:0,ty:60,rx:0,ry:60});
  assert.equal(zero.category,'stationary');assert.equal(zero.angle,null);
});

test('guide huck rules remain strict at 30 yards gain and 40 yards flight',()=>{
  assert.equal(guideMetrics({tx:-15,ty:45,rx:15,ry:75}).huck,false);
  assert.equal(guideMetrics({tx:0,ty:40,rx:0,ry:80}).huck,false);
  assert.equal(guideMetrics({tx:0,ty:40,rx:0,ry:80.1}).huck,true);
});

test('guide controls keep destination on the field while preserving requested direction',()=>{
  const start={x:20,y:115};
  assert.equal(maxGuideFlight(start,0),5);
  assert.deepEqual(guideEndpoint(start,0,50),{x:20,y:120});
  assert.deepEqual(clampGuidePoint({x:-100,y:140}),{x:-26.65,y:120});
  for(const angle of [-180,-135,-90,-45,0,45,90,135,180]){
    const end=guideEndpoint(start,angle,300);
    assert.ok(end.x>=-26.65&&end.x<=26.65&&end.y>=0&&end.y<=120);
    const actual=guideMetrics({tx:start.x,ty:start.y,rx:end.x,ry:end.y}).angle;
    assert.ok(Math.abs(Math.abs(actual)-Math.abs(angle))<1e-8);
  }
});
