"""Source-backed alternatives for the subsequent-possession project; no source edits."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SOURCE=REPO/'research/oline_possessions'
PREVIOUS=REPO/'research/possession_relationships'
SEED=20261116
DRAWS=10000

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x

def ci(values):
    finite=np.isfinite(values)
    return np.quantile(values[finite],[.025,.975]).tolist() if finite.sum()>=.95*DRAWS else None

audit=json.loads((SOURCE/'original_line_scoring.json').read_text())
prior=json.loads((PREVIOUS/'results.json').read_text())
assert audit['validation']['passed'] and prior['validation']['passed']
for rec in prior['inputs'].values():
    assert sha(REPO/rec['path'])==rec['sha256'],rec['path']
for gid,digest in audit['rawGameHashes'].items():
    assert sha(REPO/'research/dead_disc_study/raw_events'/(gid+'.json'))==digest

source_p=pd.read_csv(SOURCE/'possessions.csv')
source_t=pd.read_csv(SOURCE/'throws.csv')
assert source_p.possession_id.is_unique
assert not source_t.duplicated(['GameID','source_side','source_side_idx']).any()
assert np.array_equal(source_t.huck,((np.hypot(source_t.rx-source_t.tx,source_t.ry-source_t.ty)>40)&((source_t.ry-source_t.ty)>30)).astype(int))
included={r['possession_id'] for r in audit['rows'] if r['included']}
p=source_p[source_p.possession_id.isin(included)&source_p.first_y.notna()].copy()
assert p.outcome.isin(['goal','turnover']).all() and not p.has_timeout.any()
p['stage']=p.own_possession.clip(upper=3).astype(int)
p['distance_to_goal']=100-p.first_y
p['distance_band']=np.select([p.first_y<=20,p.first_y<=40,p.first_y<=60,p.first_y<=80],[0,1,2,3],default=4)
old=pd.read_csv(PREVIOUS/'eligible_possessions.csv')
assert set(p.loc[p.stage<=2,'possession_id'])==set(old.possession_id)
assert len(p)==6449 and p.stage.value_counts().to_dict()=={1:5474,2:838,3:137}
t=source_t.merge(p[['possession_id']],on='possession_id',validate='many_to_one')
counts=t.groupby('possession_id').agg(attempts=('huck','size'),hucks=('huck','sum'))
assert np.array_equal(p.possession_id.map(counts.attempts).fillna(0).astype(int),p.throws)
assert np.array_equal(p.possession_id.map(counts.hucks).fillna(0).astype(int),p.hucks)
t['completed_huck']=t.huck*t.complete

games=sorted(p.GameID.unique())
weights=np.random.default_rng(SEED).multinomial(len(games),np.full(len(games),1/len(games)),size=DRAWS)
def metric(frame,numerator,denominator=None,scale=1):
    q=frame[['GameID',numerator]].copy()
    q['num']=frame[numerator].to_numpy()
    q['den']=1 if denominator is None else frame[denominator].to_numpy()
    sums=q.groupby('GameID')[['num','den']].sum().reindex(games,fill_value=0).to_numpy(float)
    num,den=sums.sum(0)
    boot=weights@sums
    with np.errstate(invalid='ignore',divide='ignore'):b=scale*boot[:,0]/boot[:,1]
    return {'estimate':scale*num/den,'ci95':ci(b),'numerator':num,'denominator':den,'records':len(frame),'games':frame.GameID.nunique(),'valid_draws':int(np.isfinite(b).sum())},b

long=p[p.first_y<=40].copy()
assert long.stage.value_counts().to_dict()=={1:4802,2:457,3:75}
long_t=t[t.possession_id.isin(long.possession_id)].copy()
long_t['stage']=long_t.own_possession.clip(upper=3).astype(int)

teams=prior['scopes']['long_field']['all']['teams']
bench=prior['scopes']['long_field']['all']['league']['stages']
qx,qy=bench[0]['scoring'],bench[1]['scoring']
quadrants={name:[] for name in ['upper_left','upper_right','lower_left','lower_right']}
for team in teams:
    for stage in team['stages']:
        q=long[(long.team==team['team'])&(long.stage==stage['stage'])]
        assert len(q)==stage['possessions'] and int(q.goal.sum())==stage['goals']
        assert np.isclose(100*q.goal.mean(),stage['scoring'])
    a,b=team['stages']
    quadrants[('upper' if b['scoring']>qy else 'lower')+('_right' if a['scoring']>qx else '_left')].append(team['team'])

field=[]
for band in range(5):
    for stage in [1,2,3]:
        q=p[(p.distance_band==band)&(p.stage==stage)]
        m,b=metric(q,'goal',scale=100)
        field.append({'band':band,'stage':stage,**m})
assert sum(r['records'] for r in field)==len(p)

throws=[]
for outcome in ['all','goal','turnover']:
    q=long if outcome=='all' else long[long.outcome==outcome]
    values=[];boots=[]
    for stage in [1,2,3]:
        m,b=metric(q[q.stage==stage],'throws');values.append({'stage':stage,**m});boots.append(b)
    throws.append({'outcome':outcome,'stages':values,'change':values[1]['estimate']-values[0]['estimate'],'change_ci95':ci(boots[1]-boots[0])})
    expected=prior['scopes']['long_field'][outcome]['league']['stages']
    assert all(np.isclose(values[i]['estimate'],expected[i]['mean_throws']) for i in [0,1])

hucks=[]
for key,num,den in [('attempt_share','huck',None),('completion','completed_huck','huck')]:
    values=[];boots=[]
    for stage in [1,2,3]:
        m,b=metric(long_t[long_t.stage==stage],num,den,scale=100)
        values.append({'stage':stage,**m});boots.append(b)
    hucks.append({'metric':key,'stages':values,'change':values[1]['estimate']-values[0]['estimate'],'change_ci95':ci(boots[1]-boots[0])})

result={'createdOn':'2026-11-16','status':'complete','sourceWindow':'2026-04-24 through 2026-07-19; archived data, no live refresh',
 'coverage':{'games':len(games),'teams':22,'missing_game':'2026-07-18-PIT-CHI','known_start_possessions':len(p),'unknown_starts_excluded':len(included)-len(p),'stage_counts':p.stage.value_counts().sort_index().to_dict(),'long_field_stage_counts':long.stage.value_counts().sort_index().to_dict()},
 'bootstrap':{'draws':DRAWS,'seed':SEED,'cluster':'whole game; both teams and all stages receive the same draw weight','interval':'pointwise percentile 95%; fixed observed cohort; not simultaneous; suppressed below 95% valid draws'},
 'team_map':{'teams':teams,'benchmarks':{'first':qx,'second':qy},'quadrants':quadrants},
 'field_position':field,'throws_by_outcome':throws,'huck_profile':hucks,
 'scope':'Receiving team, original seven throughout each included possession, no within-possession timeout, goal/turnover outcomes, prior reviewed clock exclusions. All first possessions are included, not only points eventually regained. Graphs 1,3,4 start at least 60 yards from goal; graph 2 uses all known starts. The team map compares first and second; the other figures include third or later possessions.',
 'limits':['Field position is first recorded throwing location, not verified pickup; grouped positions are not exact matching.','Later possessions are selected by losing and regaining the disc. These plots do not establish fatigue or any causal effect.','Centering remains in observed throw counts; no automatic film classification is applied. A separate centering-sensitivity figure was omitted at the user’s request.','Early-huck timing remains on hold pending comparable attacking-throw definitions.','Recorded lineup continuity is not independent film verification of every substitution.'],
 'inputs':{str(path.relative_to(REPO)):sha(path) for path in [SOURCE/'possessions.csv',SOURCE/'throws.csv',SOURCE/'original_line_scoring.json',PREVIOUS/'eligible_possessions.csv',PREVIOUS/'results.json']},
 'validation':{'raw_game_hashes_verified':len(audit['rawGameHashes']),'unique_possessions':True,'unique_throw_events':True,'huck_geometry_recalculated':True,'throw_and_huck_counts_reconciled':True,'first_second_membership_matches_previous':True,'team_rates_match_previous':True,'outcome_means_match_previous':True}}
(ROOT/'results.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False)+'\n')
p[['possession_id','GameID','team','own_possession','stage','outcome','goal','throws','hucks','first_y','distance_to_goal','distance_band']].to_csv(ROOT/'eligible_possessions.csv',index=False)
print(json.dumps(clean({k:result[k] for k in ['coverage','throws_by_outcome','huck_profile']}),indent=2))
