"""Exploratory first/second check of the existing literature-based measures.

Uses the xCP figure's unchanged long-field cohort. Reports individual intervals,
within-measure 22-team intervals, and a broader 110-comparison check. No searching
across additional starting-position filters or choosing variables by p-value.
"""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SOURCE=REPO/'research/oline_possessions/throws.csv'
SEED,DRAWS,BATCH=20261116,200000,5000
base=json.loads((ROOT/'results.json').read_text())
prior=json.loads((ROOT/'team_significance.json').read_text())
for rel,digest in prior['inputs'].items():
    assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==digest,rel
p_all=pd.read_csv(ROOT/'eligible_possessions.csv')
games=sorted(p_all.GameID.unique())
p=p_all[p_all.first_y.le(40)].copy()
t_all=pd.read_csv(SOURCE)
t=t_all[t_all.possession_id.isin(set(p.possession_id))].copy()
e=pd.read_csv(ROOT/'eligible_throws.csv')
e=e[e.possession_id.isin(set(p.possession_id))]
keys=['GameID','source_side','source_side_idx']
assert not t.duplicated(keys).any() and not e.duplicated(keys).any()
check=t.merge(e,on=keys,validate='one_to_one',suffixes=('_source','_eligible'))
assert len(check)==len(t)==len(e)==42073
assert np.allclose(check.cp_source,check.cp_eligible,atol=1e-12)
assert (check.possession_id_source==check.possession_id_eligible).all()
assert (check.own_possession_source==check.own_possession_eligible).all()
assert t.cp.notna().all() and t.cp.between(0,1).all()
assert t.complete.isin([0,1]).all() and t['drop'].isin([0,1]).all()
assert t.huck.isin([0,1]).all()
assert np.array_equal(p.possession_id.map(t.groupby('possession_id').size()).fillna(0).astype(int),p.throws)
t['credited']=np.maximum(t.complete,t['drop'])
t['cpoe']=t.credited-t.cp
t['one']=1
p['one']=1

metrics={
 'xcp':{'name':'Mean expected completion probability','scale':100,'numerator':'cp','unit':'percentage points','role':'primary throwing tendency'},
 'hap':{'name':'Huck attempt percentage','scale':100,'numerator':'huck','unit':'percentage points','role':'primary throwing tendency'},
 'mean_throws':{'name':'Throws per possession','scale':1,'numerator':'throws','unit':'throws','role':'primary throwing tendency'},
 'cpoe':{'name':'Drop-credited CPOE','scale':100,'numerator':'cpoe','unit':'percentage points','role':'secondary execution'},
 'huck_completion':{'name':'Huck completion percentage','scale':100,'numerator':'complete','unit':'percentage points','role':'secondary execution'},
}
groups=[base['scopes']['long_field']['league']]+base['scopes']['long_field']['teams']
columns,records=[],[]
for key,spec in metrics.items():
    source=p if key=='mean_throws' else t[t.huck.eq(1)] if key=='huck_completion' else t
    for group in groups:
        frame=source if group['team']=='league' else source[source.team.eq(group['team'])]
        stages=[]
        for stage in [1,2]:
            q=frame[frame.own_possession.eq(stage)]
            agg=q.groupby('GameID')[[spec['numerator'],'one']].sum().reindex(games,fill_value=0)
            columns.extend([agg[spec['numerator']].to_numpy(float),agg.one.to_numpy(float)])
            num=float(q[spec['numerator']].sum());den=len(q)
            stages.append({'stage':stage,'numerator':num,'denominator':den,
                'estimate':spec['scale']*num/den if den else None,
                'games':int(q.GameID.nunique()),
                'binary_outcomes_identical':bool(den and key in ['hap','huck_completion'] and q[spec['numerator']].nunique()<2)})
        records.append({'metric':key,'team':group['team'],'team_name':group['team_name'],'stages':stages,
                        'change':stages[1]['estimate']-stages[0]['estimate'] if all(s['estimate'] is not None for s in stages) else None})
matrix=np.asarray(columns).T
scales=np.array([metrics[r['metric']]['scale'] for r in records])
rng=np.random.default_rng(SEED)
chunks=[]
for start in range(0,DRAWS,BATCH):
    w=rng.multinomial(len(games),np.full(len(games),1/len(games)),size=min(BATCH,DRAWS-start))
    sums=(w@matrix).reshape(len(w),len(records),4)
    with np.errstate(divide='ignore',invalid='ignore'):
        chunks.append(scales*(sums[:,:,2]/sums[:,:,3]-sums[:,:,0]/sums[:,:,1]))
boot=np.concatenate(chunks)
def excludes_zero(interval):
    return bool(interval and (interval[1]<0 or interval[0]>0))
for i,record in enumerate(records):
    draws=boot[:,i]; finite=np.isfinite(draws)
    valid=finite.mean()>=.95 and min(s['games'] for s in record['stages'])>=2 and not any(s['binary_outcomes_identical'] for s in record['stages'])
    record['valid_draws']=int(finite.sum());record['estimable']=bool(valid)
    record['ci95']=np.quantile(draws[finite],[.025,.975]).tolist() if valid else None
    family=5 if record['team']=='league' else 22
    record['corrected_family_size']=family
    record['corrected_interval']=np.quantile(draws[finite],[.025/family,1-.025/family]).tolist() if valid else None
    broad=5 if record['team']=='league' else 110
    record['broad_corrected_family_size']=broad
    record['broad_corrected_interval']=np.quantile(draws[finite],[.025/broad,1-.025/broad]).tolist() if valid else None
    record['individual_significant']=excludes_zero(record['ci95'])
    record['corrected_significant']=excludes_zero(record['corrected_interval'])
    record['broad_corrected_significant']=excludes_zero(record['broad_corrected_interval'])
    if record['metric']=='xcp':
        old=prior['scopes']['long_field']['league'] if record['team']=='league' else prior['scopes']['long_field']['teams'][record['team']]
        assert abs(record['change']-old['difference_pp'])<1e-9
        assert np.allclose(record['ci95'],old['ci95_pp'],atol=1e-9)
        if record['team']!='league':assert np.allclose(record['corrected_interval'],old['bonferroni_interval_pp'],atol=1e-9)

# Independent reconciliation with existing physical-throw and huck-rate results.
previous=json.loads((REPO/'research/visual_concepts_2026_11_16/calculation-summary.json').read_text())
for key,old in [('mean_throws',previous['throws_by_outcome'][0]),('hap',previous['huck_profile'][0]),('huck_completion',previous['huck_profile'][1])]:
    row=next(r for r in records if r['metric']==key and r['team']=='league')
    assert abs(row['change']-old['change'])<1e-10
    for a,b in zip(row['stages'],old['stages'][:2]):assert abs(a['estimate']-b['estimate'])<1e-10

paths=[ROOT/'eligible_possessions.csv',ROOT/'eligible_throws.csv',ROOT/'results.json',ROOT/'team_significance.json',SOURCE,
       REPO/'research/oline_possessions/literature_variable_plan_2026-11-16.json']
result={'scope':'Same as current xCP figure: original seven, first versus exactly second possession, starts at least 60 yards from goal; all physical throws including centering',
 'date':'2026-11-16','status':'complete','metrics':metrics,'draws':DRAWS,'seed':SEED,
 'method':'Two-sided percentile whole-game bootstrap; both teams and stages receive the same game weight; no p-values computed.',
 'multiplicity':'League: five-measure Bonferroni check. Teams: 22-team check within each measure, plus a stricter exploratory 110-comparison check across all five measures and 22 teams. Does not cover every earlier analysis or filter in the project.',
 'definitions':{'hap':'100 × hucks / all attempts','mean_throws':'All physical attempts / possessions','cpoe':'100 × mean(max(complete, drop) − cp); drops credited as completed under confirmed production policy','huck_completion':'100 × actual completed hucks / huck attempts; drops are unsuccessful catches'},
 'coverage':{'first_possessions':4802,'second_possessions':457,'first_attempts':39228,'second_attempts':2845,'games':131},
 'limitations':['Exploratory; variables come from existing literature-based plan but this joint testing family was selected after earlier results.','No causal inference, centering removal, or exact starting-position matching.','Huck completion and huck-share intervals are suppressed when a stage has identical binary outcomes; ordinary resampling cannot estimate that uncertainty.','No event-level aEC or LC comparison was attempted; no unavailable metrics invented.'],
 'input_hashes':{str(path.relative_to(REPO)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
 'records':records,
 'validation':{'original_xcp_means_and_intervals_reproduced':True,'all_prior_league_means_reconciled':True,'exact_eligible_throw_membership_verified':True}}
(ROOT/'other_throwing_measures.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
summary={'league':[r for r in records if r['team']=='league'],
         'teams_after_22_correction':{k:[{'team':r['team_name'],'change':r['change'],'interval':r['corrected_interval']} for r in records if r['team']!='league' and r['metric']==k and r['corrected_significant']] for k in metrics},
         'teams_after_110_correction':{k:[r['team_name'] for r in records if r['team']!='league' and r['metric']==k and r['broad_corrected_significant']] for k in metrics}}
(ROOT/'other_throwing_measures_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
