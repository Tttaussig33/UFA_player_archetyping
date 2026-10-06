export const HUCK_DISTANCE = 40;
export const HUCK_GAIN = 30;

export function passGeometry(event) {
  if (![event.tx,event.ty,event.rx,event.ry].every(Number.isFinite)) return {distance:null,gain:null,huck:false};
  const distance=Math.hypot(event.rx-event.tx,event.ry-event.ty),gain=event.ry-event.ty;
  return {distance,gain,huck:!event.stall&&distance>=HUCK_DISTANCE&&gain>=HUCK_GAIN};
}

export function connectionPlayers(events) {
  const counts=new Map();
  for(const event of events) {
    if(event.stall)continue;
    for(const id of [event.thrower,event.receiver])if(id&&id!=='unknown')counts.set(id,(counts.get(id)||0)+1);
  }
  return [...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([id])=>id);
}

export function connectionPlayerDirectory(events,players,teams) {
  const teamNames=Object.fromEntries(teams.map(team=>[team.id,team.name]));
  const memberships=new Map();
  for(const event of events)for(const id of [event.thrower,event.receiver]) {
    if(!id||id==='unknown'||!event.team)continue;
    if(!memberships.has(id))memberships.set(id,new Set());
    memberships.get(id).add(event.team);
  }
  return Object.entries(players).map(([id,player])=>{
    const teamIds=[...(memberships.get(id)||[])].sort();
    const teamLabel=teamIds.map(teamId=>teamNames[teamId]||teamId).join(', ');
    return {id,name:player.name,teamIds,label:player.name+(teamLabel?` · ${teamLabel}`:'')};
  }).sort((a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
}

export function connectionSearchTeam(player,currentTeam) {
  if(currentTeam==='all'||player.teamIds.includes(currentTeam))return currentTeam;
  return player.teamIds.length===1?player.teamIds[0]:'all';
}

export function buildConnections(events,playerId,{passType='all',outcome='complete',limit=5,name=id=>id}={}) {
  const bySide={incoming:new Map(),outgoing:new Map()};
  const eligible=events.filter(event=>!event.stall&&(event.thrower===playerId||event.receiver===playerId)
    &&(outcome==='all'||event.complete));
  const sourceRows=eligible.filter(event=>passType!=='hucks'||passGeometry(event).huck);
  for(const event of sourceRows)for(const direction of ['incoming','outgoing']) {
    if((direction==='incoming'?event.receiver:event.thrower)!==playerId)continue;
    const partnerId=(direction==='incoming'?event.thrower:event.receiver)||'unknown';
    const groups=bySide[direction];
    if(!groups.has(partnerId))groups.set(partnerId,{direction,partnerId,partner:partnerId==='unknown'?'Unrecorded player':name(partnerId),count:0,hucks:0,complete:0,events:[]});
    const group=groups.get(partnerId);
    group.count++;group.hucks+=passGeometry(event).huck?1:0;group.complete+=event.complete?1:0;group.events.push(event);
  }
  const sides={};
  for(const direction of ['incoming','outgoing']) {
    const all=[...bySide[direction].values()].sort((a,b)=>b.count-a.count||a.partner.localeCompare(b.partner)||a.partnerId.localeCompare(b.partnerId));
    const displayed=Number.isFinite(limit)?all.slice(0,limit):all.slice();
    const remainder=all.slice(displayed.length);
    if(remainder.length)displayed.push({direction,partnerId:'other',partner:`Other players (${remainder.length})`,
      count:remainder.reduce((sum,g)=>sum+g.count,0),hucks:remainder.reduce((sum,g)=>sum+g.hucks,0),
      complete:remainder.reduce((sum,g)=>sum+g.complete,0),events:remainder.flatMap(g=>g.events)});
    sides[direction]={all,displayed,total:all.reduce((sum,g)=>sum+g.count,0)};
  }
  const chartRows=['incoming','outgoing'].flatMap(direction=>sides[direction].displayed.map(group=>({
    passer:direction==='incoming'?group.partner:null,
    player:name(playerId),
    receiver:direction==='outgoing'?group.partner:null,
    passes:group.count,hucks:group.hucks,completions:group.complete,direction,partnerId:group.partnerId,
  })));
  return {sourceRows,chartRows,...sides};
}

export function selectedConnectionEvents(model,criteria=[]) {
  if(!criteria.length)return model.sourceRows;
  const ids=new Set();
  for(const row of model.chartRows)if(criteria.every(({field,name})=>String(row[field]??'')===name)) {
    const group=model[row.direction].displayed.find(g=>g.partnerId===row.partnerId);
    for(const event of group.events)ids.add(event.id);
  }
  return model.sourceRows.filter(event=>ids.has(event.id));
}
