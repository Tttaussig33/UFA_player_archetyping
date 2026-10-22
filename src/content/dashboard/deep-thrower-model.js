import {ZONES,zoneFor} from './model.js';
import {passGeometry} from './connections-model.js';

const named=id=>Boolean(id&&id!=='unknown');
const ratio=(a,b)=>b?a/b:null;

// Wilson interval describes sampling uncertainty in a binomial completion rate.
// It does not establish a causal location effect or independence between throws.
export function completionInterval(completed,attempts) {
  if(!attempts)return [null,null];
  const z=1.959963984540054,p=completed/attempts,d=1+z*z/attempts;
  const center=(p+z*z/(2*attempts))/d;
  const half=z*Math.sqrt(p*(1-p)/attempts+z*z/(4*attempts*attempts))/d;
  return [Math.max(0,center-half),Math.min(1,center+half)];
}

export function huckStats(events) {
  const completed=events.filter(e=>e.complete).length;
  const [lower,upper]=completionInterval(completed,events.length);
  return {attempts:events.length,completed,failed:events.length-completed,
    rate:ratio(completed,events.length),lower,upper};
}

// Sequence identifiers are local to a game, side, quarter, point and possession.
// Do not guess a link from row adjacency, coordinates, or a clock difference.
function contextKey(e) {
  if(!e.game||!e.team||!['quarter','point','possession'].every(k=>Number.isInteger(e[k])&&e[k]>=0))return null;
  return JSON.stringify([e.game,e.team,e.quarter,e.point,e.possession]);
}

export function precedingPasses(events) {
  const orders=new Map(),sequences=new Map(),links=new Map();
  for(const e of events) {
    const context=contextKey(e);
    if(context===null||!Number.isInteger(e.possessionThrow)||e.possessionThrow<1)continue;
    const orderKey=`${context}:${e.possessionThrow}`;
    if(!orders.has(orderKey))orders.set(orderKey,[]);
    orders.get(orderKey).push(e);
    if(Number.isFinite(e.eventSequence)) {
      const seqKey=`${context}:seq:${e.eventSequence}`;
      sequences.set(seqKey,(sequences.get(seqKey)||0)+1);
    }
  }
  for(const e of events) {
    const context=contextKey(e),order=e.possessionThrow;
    if(context===null||!Number.isInteger(order)||order<2||!named(e.thrower))continue;
    const current=orders.get(`${context}:${order}`),previous=orders.get(`${context}:${order-1}`);
    if(current?.length!==1||previous?.length!==1)continue;
    const p=previous[0];
    if(!p.complete||p.stall||p.receiver!==e.thrower)continue;
    if(!Number.isFinite(p.eventSequence)||!Number.isFinite(e.eventSequence)||p.eventSequence>=e.eventSequence)continue;
    if(sequences.get(`${context}:seq:${p.eventSequence}`)!==1||sequences.get(`${context}:seq:${e.eventSequence}`)!==1)continue;
    links.set(e.id,p);
  }
  return links;
}

export function deepThrowerComparison(events) {
  const grouped=new Map();
  for(const e of events) {
    if(e.stall||!named(e.thrower))continue;
    if(!grouped.has(e.thrower))grouped.set(e.thrower,{id:e.thrower,throws:0,locatedThrows:0,teamIds:new Set(),hucks:[]});
    const p=grouped.get(e.thrower);p.throws++;p.teamIds.add(e.team);
    const geometry=passGeometry(e);
    if(geometry.distance!==null)p.locatedThrows++;
    if(geometry.huck)p.hucks.push(e);
  }
  return [...grouped.values()].map(p=>({id:p.id,throws:p.throws,locatedThrows:p.locatedThrows,
    teamIds:[...p.teamIds],...huckStats(p.hucks),huckShare:ratio(p.hucks.length,p.locatedThrows),
    zones:ZONES.map(zone=>({...zone,...huckStats(p.hucks.filter(e=>zoneFor(e.tx,e.ty)===zone.id))})),
    unmappedReleases:p.hucks.filter(e=>!zoneFor(e.tx,e.ty)).length}))
    .sort((a,b)=>b.attempts-a.attempts||a.id.localeCompare(b.id));
}

export function rankDeepThrowers(players,{zoneId='all',minimumPlayer=20,minimumZone=5,minimumRate=null,sort='rate'}={}) {
  const stats=player=>zoneId==='all'?player:player.zones.find(zone=>zone.id===zoneId);
  return players.filter(player=>player.attempts>=minimumPlayer&&
      (zoneId==='all'||(stats(player)?.attempts??0)>=minimumZone)&&
      (!Number.isFinite(minimumRate)||(Number.isFinite(stats(player)?.rate)&&stats(player).rate>=minimumRate)))
    .sort((a,b)=>{
      const left=stats(a),right=stats(b);
      return (right[sort]??-Infinity)-(left[sort]??-Infinity)||right.attempts-left.attempts||
        (right.rate??-Infinity)-(left.rate??-Infinity)||a.id.localeCompare(b.id);
    });
}

export function buildDeepThrower(events,playerId,links=precedingPasses(events)) {
  const throws=events.filter(e=>!e.stall&&e.thrower===playerId);
  const locatedThrows=throws.filter(e=>passGeometry(e).distance!==null);
  const hucks=throws.filter(e=>passGeometry(e).huck);
  const catches=events.filter(e=>!e.stall&&e.complete&&e.receiver===playerId);
  const pairs=hucks.filter(e=>links.has(e.id)).map(huck=>({huck,previous:links.get(huck.id)}));
  const linkedCatches=pairs.map(pair=>pair.previous);
  const zones=ZONES.map(zone=>{
    const releases=hucks.filter(e=>zoneFor(e.tx,e.ty)===zone.id);
    const receipts=catches.filter(e=>zoneFor(e.rx,e.ry)===zone.id);
    const before=pairs.filter(pair=>zoneFor(pair.previous.rx,pair.previous.ry)===zone.id);
    return {...zone,...huckStats(releases),catches:receipts.length,beforeHuck:before.length,
      catchShare:ratio(receipts.length,catches.length),beforeShare:ratio(before.length,pairs.length)};
  });
  return {playerId,throws,locatedThrows,hucks,catches,pairs,linkedCatches,zones,
    ...huckStats(hucks),huckShare:ratio(hucks.length,locatedThrows.length),
    unmappedReleases:hucks.filter(e=>!zoneFor(e.tx,e.ty)).length,
    unmappedCatches:catches.filter(e=>!zoneFor(e.rx,e.ry)).length,
    unmappedLinked:linkedCatches.filter(e=>!zoneFor(e.rx,e.ry)).length};
}

export function selectHucks(model,selection) {
  if(!selection)return model.hucks;
  if(selection.kind==='receive')return model.pairs.filter(pair=>zoneFor(pair.previous.rx,pair.previous.ry)===selection.zoneId).map(pair=>pair.huck);
  if(selection.kind==='setup') {
    const previous=new Map(model.pairs.map(pair=>[pair.huck.id,pair.previous]));
    return model.hucks.filter(e=>priorPassDirection(previous.get(e.id))===selection.setupId&&
      (!selection.zoneId||selection.zoneId==='all'||zoneFor(e.tx,e.ty)===selection.zoneId));
  }
  return model.hucks.filter(e=>zoneFor(e.tx,e.ty)===selection.zoneId);
}

export const HUCK_SETUPS=[
  {id:'forward',label:'Forward pass',detail:'More forward gain than sideways travel'},
  {id:'lateral',label:'Lateral pass',detail:'Sideways travel at least as large as forward/backward travel'},
  {id:'backward',label:'Backward pass',detail:'More backward gain than sideways travel'},
  {id:'unclassified',label:'Unclassified setup',detail:'No verified prior pass, missing coordinates, or zero recorded distance'},
];

// These describe the incoming disc vector, never a player's cutting route.
export function priorPassDirection(previous) {
  if(!previous||![previous.tx,previous.ty,previous.rx,previous.ry].every(Number.isFinite))return 'unclassified';
  const dx=previous.rx-previous.tx,dy=previous.ry-previous.ty;
  if(dx===0&&dy===0)return 'unclassified';
  if(dy>Math.abs(dx))return 'forward';
  if(-dy>Math.abs(dx))return 'backward';
  return 'lateral';
}

export function buildHuckSetups(model,links,releaseZoneId='all') {
  const throws=model.throws.filter(e=>releaseZoneId==='all'||zoneFor(e.tx,e.ty)===releaseZoneId);
  const located=throws.filter(e=>passGeometry(e).distance!==null);
  const summarize=rows=>{
    const hucks=rows.filter(e=>passGeometry(e).huck);
    return {...huckStats(hucks),nextThrows:rows.length,huckShare:ratio(hucks.length,rows.length),hucks};
  };
  return {throws,missingGeometry:throws.length-located.length,...summarize(located),
    groups:HUCK_SETUPS.map(setup=>({...setup,...summarize(located.filter(e=>priorPassDirection(links.get(e.id))===setup.id))}))};
}

export function bestReleaseZone(model,minimum=5) {
  return model.zones.filter(z=>z.attempts>=minimum&&Number.isFinite(z.rate))
    .sort((a,b)=>b.rate-a.rate||b.attempts-a.attempts||a.id.localeCompare(b.id))[0]||null;
}

export function sequenceSource(hucks,links) {
  return [...new Map(hucks.flatMap(e=>links.has(e.id)?[links.get(e.id),e]:[e]).map(e=>[e.id,e])).values()];
}
