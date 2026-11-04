import {passGeometry} from './connections-model.js';

// Both comparisons keep drops and unnamed targets. Stalls are not physical throws.
export function longThrowsModel(events,playerId,type='long') {
  const allPasses=events.filter(e=>e.thrower===playerId&&!e.stall);
  const located=allPasses.filter(e=>passGeometry(e).distance!==null);
  const rows=located.filter(e=>{
    const geometry=passGeometry(e);
    return type==='hucks'?geometry.huck:geometry.distance>=40;
  });
  const completed=rows.filter(e=>e.complete).length;
  return {allPasses,rows,completed,attempts:rows.length,
    completion:rows.length?completed/rows.length:null,
    share:allPasses.length?rows.length/allPasses.length:null,
    missingLocations:allPasses.length-located.length};
}

export const LONG_FIELD={width:640,height:320,left:36,top:40,scale:4.5};
export function fieldPoint(x,y) {
  // Rotate the familiar attack-up field clockwise: attack right, source +X down.
  const drawnX=Math.max(-26.65,Math.min(26.65,x));
  return [LONG_FIELD.left+y*LONG_FIELD.scale,LONG_FIELD.top+(drawnX+26.65)*LONG_FIELD.scale];
}

// A narrow HTML hit target lets the public ChartMark own tooltip/action behavior.
export function throwHitArea(e) {
  const a=fieldPoint(e.tx,e.ty),b=fieldPoint(e.rx,e.ry),dx=b[0]-a[0],dy=b[1]-a[1];
  const length=Math.hypot(dx,dy);
  if(!length)return 'polygon(0 0,0 0,0 0)';
  const ux=dx/length,uy=dy/length,pad=5;
  const points=[
    [a[0]-ux*pad-uy*pad,a[1]-uy*pad+ux*pad],
    [b[0]+ux*pad-uy*pad,b[1]+uy*pad+ux*pad],
    [b[0]+ux*pad+uy*pad,b[1]+uy*pad-ux*pad],
    [a[0]-ux*pad+uy*pad,a[1]-uy*pad-ux*pad],
  ];
  return `polygon(${points.map(([x,y])=>`${x/LONG_FIELD.width*100}% ${y/LONG_FIELD.height*100}%`).join(',')})`;
}

export function longThrowRecords(model,player,names) {
  return model.rows.map(e=>({id:e.id,player:player.name,team:player.teamName,game:e.game,
    receiver:names[e.receiver]||'Unrecorded target',
    length:passGeometry(e).distance,forwardGain:passGeometry(e).gain,
    outcome:e.complete?'Complete':e.drop?'Drop':'Incomplete',
    throwingX:e.tx,throwingY:e.ty,targetX:e.rx,targetY:e.ry}));
}
