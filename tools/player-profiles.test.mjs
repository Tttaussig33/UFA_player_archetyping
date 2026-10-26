import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {styleDistance,rankStyleCandidates,comparisonRows,cleanProfileSearch} from '../src/content/dashboard/profile-model.js';
const result=JSON.parse(fs.readFileSync(new URL('../analysis/archetype_candidate_validation.json',import.meta.url)));
const study=result.clusterStudies.at(-1);
const reference=Object.entries(result.features).map(([feature,meta])=>({feature,...meta,sd:study.scalerSD[feature],weight:study.weights[feature]}));
test('similarity uses only style and excludes self / same-team candidates',()=>{
  const p=result.profiles.find(p=>p.id==='aatkins');
  assert.equal(styleDistance(p,{...p,name:'Changed',team:'glory',completionRate:0,throws:9999},reference),0);
  assert.equal(styleDistance(p,{...p,huckShare:NaN},reference),null);
  const matches=rankStyleCandidates(p,result.profiles,reference);
  assert.ok(matches.length>5&&matches.every(c=>c.id!==p.id&&c.team!==p.team));
  for(let i=1;i<matches.length;i++)assert.ok(matches[i].distance>=matches[i-1].distance);
  const q=matches[0];
  const manual=Math.sqrt(reference.reduce((v,r)=>v+r.weight*((p[r.feature]-q[r.feature])/r.sd)**2,0));
  assert.equal(q.distance,manual);
  assert.equal(styleDistance(p,q,reference),styleDistance(q,p,reference));
  assert.equal(rankStyleCandidates(p,result.profiles,reference,false).length,result.profiles.length-1);
  assert.equal(comparisonRows(p,q,reference).length,9);
  assert.equal(comparisonRows(p,q,reference)[0].difference,q.shortShare-p.shortShare);
  assert.equal(cleanProfileSearch('De Marrée'),'de marree');
});
test('declared four style dimensions have equal weights',()=>{
  const groups={};
  for(const r of reference)groups[r.group]=(groups[r.group]||0)+r.weight;
  assert.equal(Object.keys(groups).length,4);
  for(const weight of Object.values(groups))assert.equal(weight,.25);
});
