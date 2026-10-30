import {cleanProfileSearch} from './profile-model.js';

export const THROWER_SORTS = {
  throws:'Most passes', name:'Player name', meanGain:'Most forward gain / pass',
  shortShare:'Most short passing', lateralShare:'Most lateral passing',
  throwingY:'Farthest upfield', throwerAec:'Highest total thrower aEC',
  completionRate:'Highest completion %',
};

export function throwerDirectory(profiles, {team='all', search='', sort='throws'}={}) {
  const query=cleanProfileSearch(search).trim();
  const field=Object.hasOwn(THROWER_SORTS,sort)?sort:'throws';
  return profiles.filter(p=>(team==='all'||p.team===team)&&cleanProfileSearch(`${p.name} ${p.teamName}`).includes(query))
    .sort((a,b)=>field==='name'?a.name.localeCompare(b.name):
      (Number.isFinite(b[field])?b[field]:-Infinity)-(Number.isFinite(a[field])?a[field]:-Infinity)||a.name.localeCompare(b.name));
}

export const PASSING_TRAITS = [
  {field:'forwardShare',label:'Forward passes',unit:'share'},
  {field:'lateralShare',label:'Lateral passes',unit:'share'},
  {field:'shortShare',label:'Short passes · ≤10 yd',unit:'share'},
  {field:'huckShare',label:'Hucks',unit:'share'},
];
export const DISTANCE_TRAITS = [
  {field:'meanGain',label:'Forward gain / pass',unit:'yards'},
  {field:'nonHuckMeanGain',label:'Gain / pass, excluding hucks',unit:'yards'},
  {field:'meanFlight',label:'Flight distance / pass',unit:'yards'},
  {field:'throwingY',label:'Average throwing location',unit:'yards'},
  {field:'sidelineShare',label:'Near-sideline throws',unit:'share'},
  {field:'backwardShare',label:'Backward passes',unit:'share'},
];
export const OUTCOME_TRAITS = [
  {field:'completionRate',label:'Actual completion',unit:'share'},
  {field:'xcp',label:'Expected completion · xCP',unit:'share'},
  {field:'sourceCpoe',label:'CPOE · drop credit',unit:'pp'},
  {field:'throwerAec',label:'Total thrower aEC',unit:'number'},
  {field:'assists',label:'Assists',unit:'count'},
  {field:'hockeyAssists',label:'Verified pre-assists',unit:'count'},
];

export function throwerComparison(player, candidate, reference, traits) {
  if(!player)return [];
  const medians=Object.fromEntries(reference.map(r=>[r.feature,r.median]));
  return traits.map(t=>({...t, player:player.name, comparison:candidate?.name||'League median',
    playerValue:player[t.field]??null, comparisonValue:(candidate?candidate[t.field]:medians[t.field])??null}));
}

const DESCRIPTION_TRAITS=[
  {field:'shortShare',label:'short passes',unit:'share'},
  {field:'lateralShare',label:'lateral passes',unit:'share'},
  {field:'meanGain',label:'forward gain per pass',unit:'yards'},
  {field:'throwingY',label:'average throwing location',unit:'yards'},
  {field:'sidelineShare',label:'near-sideline throws',unit:'share'},
];

export function observedThrowingTraits(player, reference) {
  if(!player)return [];
  const medians=Object.fromEntries(reference.map(r=>[r.feature,r.median]));
  return DESCRIPTION_TRAITS.filter(t=>Number.isFinite(player[t.field])&&Number.isFinite(player[`${t.field}Percentile`])&&Number.isFinite(medians[t.field]))
    .map(t=>({...t,value:player[t.field],median:medians[t.field],departure:Math.abs(player[`${t.field}Percentile`]-50)}))
    .sort((a,b)=>b.departure-a.departure).slice(0,2);
}
