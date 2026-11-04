import {averageAngleLabel,distanceAngleModel} from './distance-angle-model.js';

export function angleDifference(a,b) {
  if(!Number.isFinite(a)||!Number.isFinite(b))return null;
  return Math.abs(((a-b+180)%360+360)%360-180);
}

// Index once instead of scanning the league's events separately for every player.
export function indexPlayerThrows(events) {
  const indexed=new Map();
  for(const event of events){
    if(event.stall||!event.thrower||event.thrower==='unknown')continue;
    if(!indexed.has(event.thrower))indexed.set(event.thrower,[]);
    indexed.get(event.thrower).push(event);
  }
  return indexed;
}

export function distanceAngleLeague(indexed,players,lower,upper) {
  return players.map(player=>({player,model:distanceAngleModel(indexed.get(player.id)||[],player.id,lower,upper)}));
}

export function validMinimumThrows(value) {
  return String(value).trim()!==''&&Number.isInteger(Number(value))&&Number(value)>=1;
}

export function findPlayers(league,{mode='arrows',referenceId,tolerance=15,direction='all',minimum=20,team='all',sort='closest'}={}) {
  const reference=league.find(entry=>entry.player.id===referenceId);
  const referenceAngle=reference?.model.averageAngle??null;
  const valid=validMinimumThrows(minimum)&&(mode==='arrows'
    ?Number.isFinite(tolerance)&&tolerance>=0&&tolerance<=180
    :direction==='all'||/^(?:[0-9]|1[01])$/.test(direction));
  if(!valid)return {rows:[],referenceAngle,reference,valid:false};
  const rows=[];
  for(const {player,model} of league){
    if(team!=='all'&&player.team!==team)continue;
    const gap=angleDifference(model.averageAngle,referenceAngle);
    if(mode==='arrows'&&(player.id===referenceId||gap===null||gap>tolerance))continue;
    const matching=mode==='throws'&&direction!=='all'?model.groups[Number(direction)].rows:model.rows;
    if(matching.length<Number(minimum))continue;
    const completed=matching.filter(e=>e.complete).length;
    rows.push({id:player.id,name:player.name,team:player.team,teamName:player.teamName,
      averageAngle:model.averageAngle,averageArrow:averageAngleLabel(model.averageAngle),averageDistance:model.averageDistance,angleDifference:gap,
      attempts:matching.length,completed,completion:completed/matching.length,
      share:model.allPasses.length?matching.length/model.allPasses.length:null,
      rangeAttempts:model.count,allAttempts:model.allPasses.length,directionalAttempts:model.directional.length,
      missingLocations:model.missingLocations,missingDirections:model.missingDirections});
  }
  rows.sort((a,b)=>{
    const order=sort==='closest'&&mode==='arrows'?a.angleDifference-b.angleDifference:
      sort==='share'?(b.share??-1)-(a.share??-1):sort==='completion'?b.completion-a.completion:b.attempts-a.attempts;
    return order||b.attempts-a.attempts||a.name.localeCompare(b.name)||a.id.localeCompare(b.id);
  });
  return {rows,referenceAngle,reference,valid:true};
}

export function finderEvidence(league,rows,referenceId) {
  const included=new Set(rows.map(row=>row.id));
  if(referenceId)included.add(referenceId);
  return league.filter(entry=>included.has(entry.player.id)).flatMap(entry=>entry.model.allPasses);
}
