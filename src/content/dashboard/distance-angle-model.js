import {throwLength} from './throwing-focus-model.js';
import {directionAngle} from './radial-model.js';

export function circularMean(angles) {
  const valid=angles.filter(Number.isFinite);
  if(!valid.length)return null;
  const sine=valid.reduce((sum,a)=>sum+Math.sin(a*Math.PI/180),0)/valid.length;
  const cosine=valid.reduce((sum,a)=>sum+Math.cos(a*Math.PI/180),0)/valid.length;
  // A numerical-zero resultant has no unique direction (e.g. equal opposite throws).
  if(Math.hypot(sine,cosine)<1e-12)return null;
  const angle=Math.atan2(sine,cosine)*180/Math.PI;
  return Math.abs(angle)<1e-10?0:angle;
}

export function directionLabel(index) {
  const start=index*30,end=start+30;
  return index<6?`${start}–${end}° left`:`${360-end}–${360-start}° right`;
}

export function averageAngleLabel(angle) {
  if(!Number.isFinite(angle))return 'No single average';
  const signed=((angle+180)%360+360)%360-180;
  const rounded=Number(Math.abs(signed).toFixed(1));
  if(rounded===0)return '0° straight forward';
  if(rounded===180)return '180° backward';
  return `${rounded.toFixed(1)}° ${signed>0?'left':'right'} of forward`;
}

export function validDistanceRange(lower,upper) {
  return lower!==''&&upper!==''&&Number.isFinite(Number(lower))&&Number.isFinite(Number(upper))&&Number(lower)>=0&&Number(upper)>Number(lower);
}

export function distanceAngleModel(events,playerId,lower=0,upper=Infinity) {
  const allPasses=events.filter(e=>e.thrower===playerId&&!e.stall);
  const located=allPasses.filter(e=>throwLength(e)!==null);
  const rows=located.filter(e=>throwLength(e)>=lower&&throwLength(e)<upper);
  const directional=rows.filter(e=>throwLength(e)>0&&directionAngle(e.throwAngle)!==null);
  const groups=Array.from({length:12},(_,index)=>{
    const matching=directional.filter(e=>Math.floor(directionAngle(e.throwAngle)/30)===index);
    return {id:String(index),index,startAngle:index*30,endAngle:(index+1)*30,label:directionLabel(index),
      rows:matching,count:matching.length,share:directional.length?matching.length/directional.length:null,
      completed:matching.filter(e=>e.complete).length};
  });
  const largestCount=Math.max(0,...groups.map(g=>g.count));
  return {allPasses,rows,directional,groups,
    missingLocations:allPasses.length-located.length,missingDirections:rows.length-directional.length,
    count:rows.length,share:allPasses.length?rows.length/allPasses.length:null,
    averageDistance:rows.length?rows.reduce((sum,e)=>sum+throwLength(e),0)/rows.length:null,
    averageAngle:circularMean(directional.map(e=>e.throwAngle)),
    leaders:largestCount?groups.filter(g=>g.count===largestCount):[],
  };
}

export function directionScale(models) {
  const largest=Math.max(0,...models.flatMap(m=>m.groups.map(g=>g.share??0)));
  return Math.max(.05,Math.ceil(largest*20)/20);
}

export function directionDisplayRows(model,player) {
  return model.groups.map(({rows,...group})=>({...group,player:player.name,playerId:player.id,
    selectedAttempts:model.count,directionalAttempts:model.directional.length,
    shareOfAllThrows:model.share,averageDistance:model.averageDistance,averageAngle:model.averageAngle}));
}
