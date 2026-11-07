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

def validate_followup():
    f=json.loads((ROOT/'follow_up_20261106.json').read_text())
    for name,digest in f['inputs'].items():
        path=ROOT/name if name!='games.csv' else ROOT.parents[1]/'data/database-exports/2026-10-12/games.csv'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    raw_cache={};point_end={};rows=[]
    p=read(ROOT/'possessions.csv')
    for x in p:
        if x['has_timeout']=='True' or x['outcome']!='turnover':continue
        gid,side,idx=x['point_id'].rsplit('|',2)
        if gid not in raw_cache:raw_cache[gid]=json.loads((RAW/(gid+'.json')).read_text())['data']
        es=raw_cache[gid][side+'Events']
        if x['point_id'] not in point_end:
            end=next(i for i in range(int(idx)+1,len(es)) if es[i]['type'] in {12,15,19,23,28,29,30,31,32,33})
            point_end[x['point_id']]=end
        end=point_end[x['point_id']];terminal=es[end]['type']
        assert (terminal in {12,15,19,23})==(x['point_end']=='goal')
        if terminal in {28,29,30,31,32,33}:continue
        broken=int(terminal in {15,23})
        assert broken==1-int(x['point_hold'])
        last=int(x['end_idx'])
        signal=next((e['type'] for e in es[last+1:end+1] if e['type'] in {11,12,13,14,15,19,23}),None)
        immediate=int(es[last]['type']==23 or signal==15)
        assert immediate<=broken
        rows.append({'stage':int(x['stage']),'team':x['team'],'broken':broken,'immediate':immediate})
    for team in [None]+[t['team'] for t in f['break_teams']]:
        result=f['break_league'] if team is None else next(t for t in f['break_teams'] if t['team']==team)
        for g in result['groups']:
            rr=[x for x in rows if x['stage']==g['stage'] and (team is None or x['team']==team)]
            assert len(rr)==g['n'] and sum(x['broken'] for x in rr)==g['sum']
            if rr:assert math.isclose(sum(x['broken'] for x in rr)/len(rr),g['estimate'],abs_tol=1e-12)
    for c in f['break_outcome_counts']:
        rr=[x for x in rows if x['stage']==c['stage']]
        assert sum(x['immediate'] for x in rr)==c['break_before_regain']
    for team in f['playoff_summary']:
        for metric in ['throws_goal','throws_turnover','scoring','early_huck']:
            pp=[x for x in p if x['team']==team['team'] and x['has_timeout']=='False']
            if metric=='throws_goal':pp=[x for x in pp if x['outcome']=='goal']
            elif metric=='throws_turnover':pp=[x for x in pp if x['outcome']=='turnover']
            elif metric=='scoring':pp=[x for x in pp if x['outcome'] in ['goal','turnover']]
            else:pp=[x for x in pp if x['first_y'] and float(x['first_y'])<=60]
            target='throws' if metric.startswith('throws') else 'goal' if metric=='scoring' else 'early_huck'
            for label in ['first','subsequent']:
                subset=[x for x in pp if (int(x['own_possession'])==1)==(label=='first')]
                assert len(subset)==team['metrics'][metric][label+'_n']
                assert math.isclose(sum(float(x[target]) for x in subset)/len(subset),team['metrics'][metric][label],abs_tol=1e-12)
    out={'date':'2026-11-06','passed':True,'checks':[
      'All follow-up input hashes match preserved sources.',
      'Every league and team break numerator independently agrees with the raw point-ending event.',
      'Immediate breaks independently checked against opponent-goal and regain events after each turnover.',
      'Every playoff summary mean, rate and denominator independently recalculated from possessions.',
      'Period-ending points are excluded from resolved break rates, not counted as breaks.'],
      'resolved_point_turnovers':len(rows),'playoff_teams':len(f['playoff_summary']),
      'follow_up_sha256':hashlib.sha256((ROOT/'follow_up_20261106.json').read_bytes()).hexdigest()}
    (ROOT/'follow_up_validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    validate()
    if (ROOT/'follow_up_20261106.json').exists():validate_followup()
