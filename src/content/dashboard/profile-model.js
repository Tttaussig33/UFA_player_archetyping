// Similarity describes measured style, never projected replacement performance.
export const cleanProfileSearch = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();

export function styleDistance(player,candidate,reference) {
  if(!player||!candidate||!reference?.length)return null;
  let sum=0;
  for(const {feature,sd,weight} of reference) {
    if(!Number.isFinite(player[feature])||!Number.isFinite(candidate[feature])||!(sd>0)||!(weight>0))return null;
    sum+=weight*((player[feature]-candidate[feature])/sd)**2;
  }
  return Math.sqrt(sum);
}

export function rankStyleCandidates(player,profiles,reference,otherTeams=true) {
  if(!player)return [];
  return profiles.filter(p=>p.id!==player.id&&(!otherTeams||p.team!==player.team))
    .map(p=>({...p,distance:styleDistance(player,p,reference)})).filter(p=>p.distance!==null)
    .sort((a,b)=>a.distance-b.distance||a.id.localeCompare(b.id));
}

export function comparisonRows(player,candidate,reference) {
  if(!player)return [];
  return reference.map(r=>({feature:r.feature,trait:r.label,group:r.group,unit:r.storedUnit,
    player:player.name,playerValue:player[r.feature],candidate:candidate?.name??null,
    candidateValue:candidate?.[r.feature]??null,
    difference:candidate?candidate[r.feature]-player[r.feature]:null}));
}
