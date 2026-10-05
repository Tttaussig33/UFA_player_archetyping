export const ZONES = [
  { id:'ez-deep', label:'Deep end zone', x0:-26.65,x1:26.65,y0:110,y1:120 },
  { id:'ez-left', label:'Left end zone', x0:-26.65,x1:0,y0:100,y1:110 },
  { id:'ez-right', label:'Right end zone', x0:0,x1:26.65,y0:100,y1:110 },
  { id:'left-attack', label:'Left attacking sideline', x0:-26.65,x1:-15,y0:60,y1:100 },
  { id:'center-red', label:'Central red zone', x0:-15,x1:15,y0:80,y1:100 },
  { id:'right-attack', label:'Right attacking sideline', x0:15,x1:26.65,y0:60,y1:100 },
  { id:'center-attack', label:'Central attack', x0:-15,x1:15,y0:60,y1:80 },
  { id:'left-build', label:'Left build-up sideline', x0:-26.65,x1:-15,y0:20,y1:60 },
  { id:'center-build', label:'Central build-up', x0:-15,x1:15,y0:40,y1:60 },
  { id:'right-build', label:'Right build-up sideline', x0:15,x1:26.65,y0:20,y1:60 },
  { id:'center-init', label:'Central initiation', x0:-15,x1:15,y0:20,y1:40 },
  { id:'own-endzone', label:'Own end zone', x0:-26.65,x1:26.65,y0:0,y1:20 },
];
export function fieldZones(metric='throw',bottom='field') {
  return ZONES.map(z=>z.id==='own-endzone'&&(metric==='original'||bottom==='callahan')
    ? {...z,label:'Callahan interceptions',role:'callahan'}
    : {...z,role:metric==='original'?(z.y0>=100?'receive':'throw'):metric});
}
export const fmt = (n, digits=2) => n==null || !Number.isFinite(n) ? '—' : n.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits});
export const int = n => n.toLocaleString('en-US');
export const clampX = x => Math.max(-26.65,Math.min(26.65,x));
export function zoneFor(x,y) {
  if (!Number.isFinite(x)||!Number.isFinite(y)||x < -26.67-1e-8||x>26.67+1e-8||y<0||y>120) return null;
  x=clampX(x);
  if(y<20)return 'own-endzone';
  if(y>=100)return y>=110?'ez-deep':x<0?'ez-left':'ez-right';
  return mainFieldZone(x,y);
}
function mainFieldZone(x,y) {
  if(x < -15)return y<60?'left-build':'left-attack';
  if(x >=15)return y<60?'right-build':'right-attack';
  return y<40?'center-init':y<60?'center-build':y<80?'center-attack':'center-red';
}
function originalZoneFor(x,y,role) {
  const zone=zoneFor(x,y);
  if(!zone)return null;
  if(role==='receive')return y>=100?zone:null;
  // The first adaptation included releases on y=100 in the main field.
  return y>=20&&y<=100?mainFieldZone(clampX(x),y):null;
}
export function zoneBuckets(events,callahans,metric='throw',bottom='field') {
  const buckets=Object.fromEntries(ZONES.map(z=>[z.id,[]]));
  for(const e of events) {
    if(metric==='combined') {
      const t=zoneFor(e.tx,e.ty);
      if(t)buckets[t].push({...e,creditRole:'throw'});
      if(e.receiver&&(e.complete||e.drop)) {
        const r=zoneFor(e.rx,e.ry);
        if(r)buckets[r].push({...e,creditRole:'receive'});
      }
      continue;
    }
    if(metric==='original') {
      const t=originalZoneFor(e.tx,e.ty,'throw');
      if(t)buckets[t].push(e);
      if(e.receiver&&(e.complete||e.drop)) {
        const r=originalZoneFor(e.rx,e.ry,'receive');
        if(r)buckets[r].push(e);
      }
      continue;
    }
    if(metric==='receive'&&!(e.receiver&&(e.complete||e.drop)))continue;
    const z=metric==='throw'?zoneFor(e.tx,e.ty):zoneFor(e.rx,e.ry);
    if(z)buckets[z].push(e);
  }
  if(metric==='original'||bottom==='callahan')buckets['own-endzone']=callahans;
  return buckets;
}
export function rankZone(rows,role) {
  const people=new Map();
  for(const e of rows) {
    const contribution=eventRole(e,role),id=eventPlayer(e,role);
    if(!id||id==='unknown')continue;
    if(!people.has(id))people.set(id,{id,count:0,completed:0,aec:0,scored:0,events:[],throwCount:0,receiveCount:0,throwScored:0,receiveScored:0,throwAec:0,receiveAec:0});
    const p=people.get(id),a=eventAec(e,role);
    p.count++;p.completed+=role==='callahan'||e.complete?1:0;p.events.push(e);
    if(Number.isFinite(a)){p.aec+=a;p.scored++;}
    if(contribution==='throw'||contribution==='receive') {
      p[`${contribution}Count`]++;
      if(Number.isFinite(a)){p[`${contribution}Aec`]+=a;p[`${contribution}Scored`]++;}
    }
  }
  return [...people.values()].map(p=>({...p,aec:p.scored?p.aec:null,rate:p.count?p.completed/p.count:null,
    throwAec:p.throwScored||!p.throwCount?p.throwAec:null,receiveAec:p.receiveScored||!p.receiveCount?p.receiveAec:null}))
    .sort((a,b)=>(b.aec??-Infinity)-(a.aec??-Infinity)||b.count-a.count||a.id.localeCompare(b.id));
}
export const eventRole = (event,role) => role==='combined'?event.creditRole:role;
export const eventPlayer = (event,role) => eventRole(event,role)==='throw'?event.thrower:eventRole(event,role)==='receive'?event.receiver:event.player;
export const eventAec = (event,role) => eventRole(event,role)==='throw'?event.throwAec:eventRole(event,role)==='receive'?event.receiveAec:event.aec;
// Combined buckets contain role contributions; source inspection retains each
// underlying reviewed throw once, without its derived role annotation.
export function sourceEvents(rows) {
  return [...new Map(rows.map(({creditRole,...event})=>[event.id,event])).values()];
}
export const roleLabel = role => role==='combined'?'Overall aEC':role==='throw'?'Thrower aEC':role==='receive'?'Receiver aEC':'Callahan aEC';
export const units = role => role==='combined'?'throws + targets':role==='throw'?'throws':role==='receive'?'targets':'interceptions';
