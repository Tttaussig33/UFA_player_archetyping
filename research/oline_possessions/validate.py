"""Independent aggregate reconciliation and source checks for this study."""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import math
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
RAW=ROOT.parent/'dead_disc_study/raw_events'

def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))

def validate():
    p=read(ROOT/'possessions.csv');t=read(ROOT/'throws.csv');pts=read(ROOT/'points.csv')
    r=json.loads((ROOT/'results.json').read_text());a=json.loads((ROOT/'cohort_audit.json').read_text())
    checks=[]
    for name,digest in r['inputs'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    checks.append('Analysis input hashes match the current cohort and specification.')
    key=lambda x:(x['GameID'],x['source_side'],x['source_side_idx'])
    old=read(ROOT.parent/'huck_timing_study/oline_regains/throw_cohort.csv')
    oldmap={key(x):x for x in old};assert set(oldmap)=={key(x) for x in t}
    for x in t:
        y=oldmap[key(x)]
        for field in ['ordinal','huck','complete','drop','tx','ty','rx','ry']:
            assert float(x[field])==float(y[field]),(key(x),field)
        assert int(x['own_possession'])==int(y['attacking_possession'])
    checks.append('All 52,997 physical throws and original ordinals match the earlier independently audited cohort.')
    bypos=defaultdict(list);bypoint=defaultdict(list)
    for x in t:bypos[x['possession_id']].append(x)
    for x in p:
        ts=bypos[x['possession_id']]
        assert len(ts)==int(x['throws'])
        assert sorted(int(z['ordinal']) for z in ts)==list(range(1,len(ts)+1))
        assert int(x['has_huck'])==int(any(int(z['huck']) for z in ts))
        assert int(x['early_huck'])==int(any(int(z['huck']) and int(z['ordinal'])<=3 for z in ts))
        assert int(x['goal'])==int(x['outcome']=='goal')
        for z in ts:assert z['has_timeout']==x['has_timeout']
        bypoint[x['point_id']].append(x)
    for point,ps in bypoint.items():
        ps=sorted(ps,key=lambda x:int(x['own_possession']))
        assert [int(x['own_possession']) for x in ps]==list(range(1,len(ps)+1))
        assert all(x['outcome']=='turnover' for x in ps[:-1])
        prior=0
        for x in ps:
            assert int(x['prior_own_throws'])==prior
            prior+=int(x['throws'])
    for pt in pts:
        assert sum(int(x['goal']) for x in bypoint[pt['point_id']])==int(pt['hold'])
    checks.append('Possession endings, zero-throw outcomes, prior own-team activity and eventual point holds reconcile.')
    pp=[x for x in p if x['has_timeout']=='False'];tt=[x for x in t if x['has_timeout']=='False']
    assert len(pp)==r['scope']['possessions'] and len(tt)==r['scope']['physical_throws']
    assert len(p)-len(pp)==146
    metrics={
      'scoring':([x for x in pp if x['outcome']!='period_end'],'goal'),
      'throws_goal':([x for x in pp if x['outcome']=='goal'],'throws'),
      'throws_turnover':([x for x in pp if x['outcome']=='turnover'],'throws'),
      'throws_all':([x for x in pp if x['outcome']!='period_end'],'throws'),
      'early_huck':([x for x in pp if x['first_y'] and float(x['first_y'])<=60],'early_huck'),
      'any_huck':([x for x in pp if x['first_y'] and float(x['first_y'])<=60],'has_huck'),
      'huck_share':([x for x in tt if float(x['first_y'])<=60],'huck'),
      'huck_completion':([x for x in tt if float(x['first_y'])<=60 and x['huck']=='1'],'complete')}
    for metric,(records,outcome) in metrics.items():
        for team in [None]+[x['team'] for x in r['teams']]:
            result=r['league'][metric] if team is None else next(x for x in r['teams'] if x['team']==team)['metrics'][metric]
            for g in result['groups']:
                subset=[x for x in records if int(x['stage'])==g['stage'] and (team is None or x['team']==team)]
                assert len(subset)==g['n']
                total=sum(float(x[outcome]) for x in subset)
                assert total==g['sum']
                if subset:assert math.isclose(total/len(subset),g['estimate'],abs_tol=1e-12)
    checks.append('Every league and team metric independently recomputed from CSV with exact numerator and denominator agreement.')
    # Check combined prior activity directly against opponent event losses.
    raw_cache={};known=0
    for x in p:
        if x['regained']!='1' or not x['prior_opponent_throws']:continue
        gid=x['GameID'];side='away' if '|home|' in x['point_id'] else 'home'
        if gid not in raw_cache:raw_cache[gid]=json.loads((RAW/(gid+'.json')).read_text())['data']
        es=raw_cache[gid][side+'Events'];quarter=1;starts=[]
        for i,e in enumerate(es):
            if e['type']==1 and quarter==int(x['quarter']) and e.get('time')==float(x['point_start_time']):starts.append(i)
            if e['type'] in range(28,34):quarter=e['type']-26
        assert len(starts)==1
        count=loss=0
        for e in es[starts[0]+1:]:
            typ=e['type']
            if typ in {1,2,12,15,19,23,28,29,30,31,32,33}:break
            if typ in {18,20,22}:count+=1
            if typ in {20,22,24}:
                loss+=1
                if loss==int(x['own_possession'])-1:break
        assert loss==int(x['own_possession'])-1 and count==float(x['prior_opponent_throws']),x['possession_id']
        known+=1
    checks.append(f'All {known} known prior-opponent activity counts independently match raw event sequences; uncertain contexts remain missing.')
    model_count=0
    def walk(x):
        nonlocal model_count
        if isinstance(x,dict):
            if 'design_rank' in x:
                assert x['converged'] and x['design_rank']==x['columns'] and not x['warnings']
                model_count+=1
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(r)
    checks.append(f'{model_count} reported regression fits converged with full-rank designs and no captured fit warnings.')
    assert len(r['team_changes'])==6 and sum(len(v['teams']) for v in r['team_changes'].values())==132
    for v in r['team_changes'].values():
        for x in v['teams']:
            assert x['p_value']<=x['p_holm']+1e-12<=x['p_holm_across_132_team_comparisons']+1e-12
    checks.append('All 132 team contrasts retain within-metric and across-metric multiplicity corrections.')
    out={'checked_at':datetime.now(timezone.utc).isoformat(),'passed':True,'checks':checks,
         'source_limitations':{'missing_games':1,'excluded_points':len(a['excluded_points']),
           'score_discrepancy_team_streams':len(a['score_reconciliation']['mismatches']),
           'combined_prior_activity_missing_eligible_regains':r['prior_activity']['prior_total_throws']['missing']},
         'results_sha256':hashlib.sha256((ROOT/'results.json').read_bytes()).hexdigest()}
    (ROOT/'validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':validate()
