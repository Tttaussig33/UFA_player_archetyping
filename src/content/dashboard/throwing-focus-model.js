import {directionAngle} from './radial-model.js';
import {cleanProfileSearch} from './profile-model.js';

export const LENGTHS=[
  {id:'under10',label:'0–10 yards',min:0,max:10},
  {id:'10to20',label:'10–20 yards',min:10,max:20},
  {id:'20to40',label:'20–40 yards',min:20,max:40},
  {id:'40plus',label:'40+ yards',min:40,max:Infinity},
];
const DIRECTIONS=['Forward-left','Diagonal left','Left, slightly forward','Left, slightly back','Diagonal back-left','Back-left',
  'Back-right','Diagonal back-right','Right, slightly back','Right, slightly forward','Diagonal right','Forward-right'];

export function throwLength(e) {
  return [e.tx,e.ty,e.rx,e.ry].every(Number.isFinite)?Math.hypot(e.rx-e.tx,e.ry-e.ty):null;
}
export function throwResults(rows) {
  const completed=rows.filter(e=>e.complete).length,values=rows.map(e=>e.throwAec).filter(Number.isFinite);
  return {attempts:rows.length,completed,completion:rows.length?completed/rows.length:null,
    aec:values.length?values.reduce((s,v)=>s+v,0):null,missingAec:rows.length-values.length};
}
export function focusModel(events,playerId,view='length',selection=null) {
  const allPasses=events.filter(e=>e.thrower===playerId&&!e.stall);
  const eligible=allPasses.filter(e=>view==='length'?throwLength(e)!==null:throwLength(e)>0&&directionAngle(e.throwAngle)!==null);
  const groups=view==='length'?LENGTHS.map(b=>({...b,rows:eligible.filter(e=>{const d=throwLength(e);return d>=b.min&&d<b.max;})})):
    DIRECTIONS.map((label,i)=>({id:String(i),label,startAngle:i*30,endAngle:(i+1)*30,rows:eligible.filter(e=>Math.floor(directionAngle(e.throwAngle)/30)===i)}));
  for(const group of groups)Object.assign(group,throwResults(group.rows),{share:eligible.length?group.rows.length/eligible.length:null});
  const selected=groups.find(g=>g.id===selection),rows=selected?selected.rows:eligible;
  return {allPasses,eligible,groups,selected,rows,results:throwResults(rows),excluded:allPasses.length-eligible.length,
    displayRows:groups.map(({rows,min,max,...group})=>({...group,...(min!==undefined?{min,max:Number.isFinite(max)?max:null}:{})}))};
}
export function focusDirectory(rows,search='') {
  const q=cleanProfileSearch(search);
  return rows.filter(r=>cleanProfileSearch(`${r.name} ${r.teamName}`).includes(q)).sort((a,b)=>a.name.localeCompare(b.name));
}

// Source angles increase toward negative X, so left is 90° with attack up.
export function directionPoint(angle,radius,cx=180,cy=180) {
  return [cx-Math.sin(angle*Math.PI/180)*radius,cy-Math.cos(angle*Math.PI/180)*radius];
}
export function directionSlice(start,end,radius,inner=12) {
  const a=directionPoint(start+.7,inner),b=directionPoint(start+.7,radius),c=directionPoint(end-.7,radius),d=directionPoint(end-.7,inner);
  return `M${a}L${b}A${radius},${radius},0,0,0,${c}L${d}A${inner},${inner},0,0,1,${a}Z`;
}
export function directionHit(start,end) {
  const points=[[50,50],...Array.from({length:9},(_,i)=>directionPoint(start+(end-start)*i/8,40,50,50))];
  return `polygon(${points.map(p=>`${p[0]}% ${p[1]}%`).join(',')})`;
}
