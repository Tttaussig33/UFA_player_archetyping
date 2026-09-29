export const ZONES = [
  { id:'ez-deep', label:'Deep end zone', role:'receive', x0:-26.65,x1:26.65,y0:110,y1:120 },
  { id:'ez-left', label:'Left end zone', role:'receive', x0:-26.65,x1:0,y0:100,y1:110 },
  { id:'ez-right', label:'Right end zone', role:'receive', x0:0,x1:26.65,y0:100,y1:110 },
  { id:'left-attack', label:'Left attacking sideline', role:'throw', x0:-26.65,x1:-15,y0:60,y1:100 },
  { id:'center-red', label:'Central red zone', role:'throw', x0:-15,x1:15,y0:80,y1:100 },
  { id:'right-attack', label:'Right attacking sideline', role:'throw', x0:15,x1:26.65,y0:60,y1:100 },
  { id:'center-attack', label:'Central attack', role:'throw', x0:-15,x1:15,y0:60,y1:80 },
  { id:'left-build', label:'Left build-up sideline', role:'throw', x0:-26.65,x1:-15,y0:20,y1:60 },
  { id:'center-build', label:'Central build-up', role:'throw', x0:-15,x1:15,y0:40,y1:60 },
  { id:'right-build', label:'Right build-up sideline', role:'throw', x0:15,x1:26.65,y0:20,y1:60 },
  { id:'center-init', label:'Central initiation', role:'throw', x0:-15,x1:15,y0:20,y1:40 },
  { id:'callahan', label:'Callahan interceptions', role:'callahan', x0:-26.65,x1:26.65,y0:0,y1:20 },
];
export const fmt = (n, digits=2) => n==null || !Number.isFinite(n) ? '—' : n.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits});
export const int = n => n.toLocaleString('en-US');
export const clampX = x => Math.max(-26.65,Math.min(26.65,x));
export function zoneFor(x,y,role) {
  if (!Number.isFinite(x)||!Number.isFinite(y)||x < -26.67-1e-8||x>26.67+1e-8) return null;
  x=clampX(x);
  if(role==='receive') {
    if(y<100||y>120)return null;
    return y>=110?'ez-deep':x<0?'ez-left':'ez-right';
  }
  if(y<20||y>100)return null;
  if(x < -15)return y<60?'left-build':'left-attack';
  if(x >=15)return y<60?'right-build':'right-attack';
  return y<40?'center-init':y<60?'center-build':y<80?'center-attack':'center-red';
}
export function zoneBuckets(events,callahans) {
  const buckets=Object.fromEntries(ZONES.map(z=>[z.id,[]]));
  for(const e of events) {
    const t=zoneFor(e.tx,e.ty,'throw');
    if(t)buckets[t].push(e);
    if(e.receiver && (e.complete||e.drop)) {
      const r=zoneFor(e.rx,e.ry,'receive');
      if(r)buckets[r].push(e);
    }
  }
  buckets.callahan=callahans;
  return buckets;
}
export function rankZone(rows,role) {
  const people=new Map();
  for(const e of rows) {
    const id=role==='throw'?e.thrower:role==='receive'?e.receiver:e.player;
    if(!id||id==='unknown')continue;
    if(!people.has(id))people.set(id,{id,count:0,completed:0,aec:0,scored:0,events:[]});
    const p=people.get(id),a=role==='throw'?e.throwAec:role==='receive'?e.receiveAec:e.aec;
    p.count++;p.completed+=role==='callahan'||e.complete?1:0;p.events.push(e);
    if(Number.isFinite(a)){p.aec+=a;p.scored++;}
  }
  return [...people.values()].map(p=>({...p,aec:p.scored?p.aec:null,rate:p.count?p.completed/p.count:null}))
    .sort((a,b)=>(b.aec??-Infinity)-(a.aec??-Infinity)||b.count-a.count||a.id.localeCompare(b.id));
}
export const roleLabel = role => role==='throw'?'Thrower aEC':role==='receive'?'Receiver aEC':'Callahan aEC';
export const units = role => role==='throw'?'throws':role==='receive'?'targets':'interceptions';
