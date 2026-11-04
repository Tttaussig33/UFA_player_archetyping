import {passGeometry} from './connections-model.js';

export const THROW_TYPES=[
  {id:'under10',label:'0–10 yards',min:0,max:10},
  {id:'10to20',label:'10–20 yards',min:10,max:20},
  {id:'20to30',label:'20–30 yards',min:20,max:30},
  {id:'30to40',label:'30–40 yards',min:30,max:40},
  {id:'long',label:'40+ yards',min:40,max:Infinity},
  {id:'hucks',label:'Hucks'},
];

export function throwExpectation(event) {
  const expectedCompletion=Number.isFinite(event.cp)?event.cp:null;
  // Shown Space credits recorded drops to the thrower. Its raw cpoe field is
  // 1 on drops, so derive the residual from cp rather than averaging that field.
  const cpoe=expectedCompletion!==null&&!event.stall?(event.complete||event.drop?1:0)-expectedCompletion:null;
  return {expectedCompletion,cpoe,lagContribution:null};
}

export function throwExpectationSummary(rows) {
  const passes=rows.filter(e=>!e.stall),scored=passes.filter(e=>Number.isFinite(e.cp));
  const expectedCompletion=scored.length?scored.reduce((sum,e)=>sum+e.cp,0)/scored.length:null;
  const credited=passes.filter(e=>e.complete||e.drop).length;
  return {expectedCompletion,cpoe:passes.length&&expectedCompletion!==null?credited/passes.length-expectedCompletion:null,
    scoredAttempts:scored.length,missingExpectation:passes.length-scored.length};
}

// All distance bands keep drops and unnamed targets. Stalls are not physical throws.
export function longThrowsModel(events,playerId,type='long') {
  const band=THROW_TYPES.find(option=>option.id===type);
  const allPasses=events.filter(e=>e.thrower===playerId&&!e.stall);
  const located=allPasses.filter(e=>passGeometry(e).distance!==null);
  const rows=located.filter(e=>{
    const geometry=passGeometry(e);
    return type==='hucks'?geometry.huck:band&&geometry.distance>=band.min&&geometry.distance<band.max;
  });
  const completed=rows.filter(e=>e.complete).length;
  return {allPasses,rows,completed,attempts:rows.length,
    completion:rows.length?completed/rows.length:null,
    ...throwExpectationSummary(rows),
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
  if(!length)return `polygon(${[[a[0]-5,a[1]-5],[a[0]+5,a[1]-5],[a[0]+5,a[1]+5],[a[0]-5,a[1]+5]].map(([x,y])=>`${x/LONG_FIELD.width*100}% ${y/LONG_FIELD.height*100}%`).join(',')})`;
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
    outcome:e.complete?'Complete':e.drop?'Drop':'Incomplete',...throwExpectation(e),
    throwingX:e.tx,throwingY:e.ty,targetX:e.rx,targetY:e.ry}));
}
