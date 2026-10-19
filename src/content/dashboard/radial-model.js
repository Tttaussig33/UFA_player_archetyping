import {passGeometry} from './connections-model.js';

// Mirrors prod.get_player_throw_directions. The source's centerAngle is the
// lower bucket edge; the original website draws each wedge at that angle.
export function directionAngle(value) {
  return Number.isFinite(value)?((value%360)+360)%360:null;
}

export function buildRadials(events,playerId,{passType='all',outcome='all',bucketCount=12}={}) {
  const count=Math.max(4,Math.min(36,Number.isFinite(bucketCount)?Math.trunc(bucketCount):12));
  const step=360/count;
  const eligible=playerId&&playerId!=='unknown'?events.filter(event=>
    (event.thrower===playerId||event.receiver===playerId)
    &&(outcome==='all'||event.complete)
    &&(passType!=='hucks'||passGeometry(event).huck)):[];
  const sourceRows=eligible.filter(event=>directionAngle(event.throwAngle)!==null);
  const sides={};
  for(const role of ['throw','receive']) {
    const endpoint=role==='throw'?'thrower':'receiver';
    const rows=sourceRows.filter(event=>event[endpoint]===playerId);
    const groups=Array.from({length:count},(_,index)=>({index,startAngle:index*step,endAngle:(index+1)*step,
      centerAngle:index*step,label:`${Math.round(index*step)}°`,events:[]}));
    for(const event of rows)groups[Math.min(count-1,Math.floor(directionAngle(event.throwAngle)/step))].events.push(event);
    const buckets=groups.map(bucket=>({...bucket,count:bucket.events.length,
      share:rows.length?bucket.events.length/rows.length:null,
      completed:bucket.events.filter(event=>event.complete).length}));
    sides[role]={sourceRows:rows,total:rows.length,buckets,
      missingAngle:eligible.filter(event=>event[endpoint]===playerId&&directionAngle(event.throwAngle)===null).length,
      maxShare:Math.max(0,...buckets.map(bucket=>bucket.share??0))};
  }
  return {sourceRows,...sides,bucketCount:count};
}

export function radialRecords(model,selection) {
  return selection?model[selection.role].buckets[selection.index]?.events||[]:model.sourceRows;
}

// Clockwise, with 0° at the top, matching Shown Space's rendered diagrams.
export function radialPoint(angle,radius,center=200) {
  const radians=angle*Math.PI/180;
  return [center+Math.sin(radians)*radius,center-Math.cos(radians)*radius];
}

export function radialWedge(angle,width,radius,innerRadius=9.6) {
  const start=angle-width/2+.5,end=angle+width/2-.5;
  const a=radialPoint(start,innerRadius),b=radialPoint(start,radius),c=radialPoint(end,radius),d=radialPoint(end,innerRadius);
  return `M ${a.join(' ')} L ${b.join(' ')} A ${radius} ${radius} 0 0 1 ${c.join(' ')} L ${d.join(' ')} A ${innerRadius} ${innerRadius} 0 0 0 ${a.join(' ')} Z`;
}

export function radialHitArea(angle,width) {
  const points=[[50,50]];
  for(let i=0;i<=16;i++)points.push(radialPoint(angle-width/2+width*i/16,38,50));
  return `polygon(${points.map(point=>point.map(value=>`${value}%`).join(' ')).join(',')})`;
}
