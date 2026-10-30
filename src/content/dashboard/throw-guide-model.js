import {passGeometry} from './connections-model.js';

export const GUIDE_FIELD={xMin:-26.65,xMax:26.65,yMin:0,yMax:120};
export const THROW_EXAMPLES=[
  {id:'forward',label:'Forward',tx:-15,ty:45,rx:0,ry:80},
  {id:'forward-edge',label:'45° forward',tx:-15,ty:45,rx:15,ry:75},
  {id:'sideways',label:'Sideways',tx:-15,ty:60,rx:15,ry:60},
  {id:'backward-edge',label:'45° backward',tx:-15,ty:75,rx:15,ry:45},
  {id:'backward',label:'Backward',tx:-15,ty:75,rx:0,ry:40},
  {id:'huck',label:'Deep huck',tx:-15,ty:40,rx:15,ry:80},
];
const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
export const clampGuidePoint=({x,y})=>({x:clamp(x,GUIDE_FIELD.xMin,GUIDE_FIELD.xMax),y:clamp(y,0,120)});

// This is an illustrative bearing from the attacking direction, not the
// source throwAngle used by the Shown Space radial reproduction.
export function guideMetrics(event) {
  const geometry=passGeometry(event),lateral=event.rx-event.tx;
  if(geometry.distance===null)return {...geometry,lateral:null,angle:null,offset:null,category:'unknown',boundary:false};
  if(geometry.distance<1e-9)return {...geometry,lateral:0,angle:null,offset:null,category:'stationary',boundary:false};
  const angle=Math.atan2(lateral,geometry.gain)*180/Math.PI;
  // Trigonometric sliders can land a few floating-point bits off an exact
  // 45° line. Treat only that numerical noise as the boundary.
  const boundary=Math.abs(Math.abs(geometry.gain)-Math.abs(lateral))<1e-9;
  const category=!boundary&&geometry.gain>Math.abs(lateral)?'forward':!boundary&&-geometry.gain>Math.abs(lateral)?'backward':'sideways';
  return {...geometry,lateral,angle,offset:Math.min(Math.abs(angle),180-Math.abs(angle)),category,boundary};
}

function vector(angle) {
  const radians=angle*Math.PI/180;
  let x=Math.sin(radians),y=Math.cos(radians);
  if(Math.abs(x)<1e-12)x=0;
  if(Math.abs(y)<1e-12)y=0;
  if(Math.abs(Math.abs(x)-Math.abs(y))<1e-12)y=Math.sign(y)*Math.abs(x);
  return {x,y};
}

export function maxGuideFlight(start,angle) {
  const v=vector(angle),limits=[];
  if(v.x>0)limits.push((GUIDE_FIELD.xMax-start.x)/v.x);
  if(v.x<0)limits.push((GUIDE_FIELD.xMin-start.x)/v.x);
  if(v.y>0)limits.push((120-start.y)/v.y);
  if(v.y<0)limits.push(-start.y/v.y);
  return Math.max(0,Math.min(...limits));
}

export function guideEndpoint(start,angle,distance) {
  const v=vector(angle),d=clamp(distance,0,maxGuideFlight(start,angle));
  return clampGuidePoint({x:start.x+v.x*d,y:start.y+v.y*d});
}
