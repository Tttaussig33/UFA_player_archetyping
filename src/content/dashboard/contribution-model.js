import {cleanProfileSearch} from './profile-model.js';

export const CONTRIBUTIONS={
  advance:{label:'Advancement',description:'Forward-directed passes: more forward gain than sideways movement.'},
  redistribute:{label:'Redistribution',description:'Sideways or backward passes. Direction describes the pass, not the thrower’s intent.'},
  score:{label:'Scoring delivery',description:'Targets at or beyond the attacking goal line. Actual assists are counted separately.'},
};
export const CONTRIBUTION_SORTS={share:'How often they use it',cpoePp:'Completion above expected',completionRate:'Actual completion',attempts:'Attempts'};
export const percent=v=>Number.isFinite(v)?`${(v*100).toFixed(1)}%`:'—';
export const signedPp=v=>Number.isFinite(v)?`${v>=0?'+':''}${v.toFixed(1)} pp`:'—';
export const intervalText=row=>Number.isFinite(row.lowerPp)&&Number.isFinite(row.upperPp)?`${signedPp(row.lowerPp)} to ${signedPp(row.upperPp)}`:'Interval unavailable';

export function contributionDirectory(rows,{role='advance',team='all',search='',minimum=20,sort='share'}={}) {
  const query=cleanProfileSearch(search).trim(),floor=Math.max(0,Number(minimum)||0);
  const field=Object.hasOwn(CONTRIBUTION_SORTS,sort)?sort:'share';
  return rows.filter(r=>r.role===role&&(team==='all'||r.teamId===team)&&r.attempts>=floor&&cleanProfileSearch(`${r.name} ${r.teamName}`).includes(query))
    .sort((a,b)=>{
      const av=a[field],bv=b[field];
      if(Number.isFinite(av)!==Number.isFinite(bv))return Number.isFinite(av)?-1:1;
      return (Number.isFinite(av)?bv-av:0)||b.attempts-a.attempts||a.name.localeCompare(b.name);
    });
}

export function contributionPlot(rows) {
  return rows.filter(r=>r.attempts>0&&Number.isFinite(r.cpoePp)&&Number.isFinite(r.share))
    .map(r=>({...r,featureName:`${r.name} · ${r.attempts} attempts`,contributionShare:r.share}));
}

export function playerContributions(rows,playerId,baselines) {
  return Object.keys(CONTRIBUTIONS).flatMap(role=>{
    const row=rows.find(r=>r.playerId===playerId&&r.role===role);
    const baseline=baselines.find(r=>r.role===role);
    return row&&baseline?[{...row,medianShare:baseline.shareMedian,leagueCompletionRate:baseline.completionRate}]:[];
  });
}
