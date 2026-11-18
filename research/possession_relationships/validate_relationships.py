"""Independent stdlib check of cohort, numerator/denominator and correlation bindings."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
d=json.loads((ROOT/'results.json').read_text())
rows=list(csv.DictReader((ROOT/'eligible_possessions.csv').open()))
assert len({r['possession_id'] for r in rows})==len(rows)
audit=json.loads((REPO/'research/oline_possessions/original_line_scoring.json').read_text())
by_id={r['possession_id']:r for r in audit['rows']}
for source in d['inputs'].values():
    assert hashlib.sha256((REPO/source['path']).read_bytes()).hexdigest()==source['sha256']
raw={}
for r in rows:
    old=by_id[r['possession_id']]
    assert old['included'] and old['line_eligible'] and not old['has_timeout'] and int(r['own_possession']) in [1,2]
    assert old['goal']==int(r['goal'])
    assert old['physical_throws_before_cutoff']==int(r['throws'])
checks=0
for scope,groups in d['scopes'].items():
    selected=[r for r in rows if scope=='all_starts' or float(r['first_y'])<=40]
    for outcome,result in groups.items():
        subset=[r for r in selected if outcome=='all' or r['outcome']==outcome]
        aggregate=defaultdict(lambda:dict(n=0,g=0,t=0,h=0))
        for r in subset:
            a=aggregate[(r['team'],int(r['own_possession']))]
            a['n']+=1;a['g']+=int(r['goal']);a['t']+=int(r['throws']);a['h']+=int(r['hucks'])
        xs,ys,ts=[],[],[]
        for team in result['teams']:
            values=[]
            for stage in team['stages']:
                a=aggregate[(team['team'],stage['stage'])]
                assert [a[k] for k in ['n','g','t','h']]==[stage[k] for k in ['possessions','goals','attempts','hucks']]
                measures={'hap':100*a['h']/a['t'],'scoring':100*a['g']/a['n'],'mean_throws':a['t']/a['n'],'hucks_per_possession':a['h']/a['n']}
                assert all(math.isclose(stage[k],v,abs_tol=1e-12) for k,v in measures.items())
                assert math.isclose(measures['hap']/100*measures['mean_throws'],measures['hucks_per_possession'],abs_tol=1e-12)
                values.append(measures);checks+=1
            for key in values[0]:
                assert math.isclose(team['change'][key],values[1][key]-values[0][key],abs_tol=1e-12)
            xs.append(team['change']['hap']);ys.append(team['change']['scoring']);ts.append(team['change']['mean_throws'])
        if outcome=='all':
            assert math.isclose(statistics.correlation(xs,ys),result['correlations']['hucking_vs_scoring_change']['pearson'],abs_tol=1e-12)
            assert math.isclose(statistics.correlation(ts,ys),result['correlations']['throws_vs_scoring_change']['pearson'],abs_tol=1e-12)
        for key in ['hap','mean_throws']:
            seen=[]
            for quadrant,names in result['quadrants'][key].items():
                for name in names:
                    team=next(t for t in result['teams'] if t['team']==name)
                    x,y=team['change'][key],team['change']['scoring']
                    expected=('upper' if y>0 else 'lower')+('_right' if x>0 else '_left') if x!=0 and y!=0 else 'on_axis'
                    assert quadrant==expected
                    seen.append(name)
            assert len(seen)==len(set(seen))==22
        assert math.isclose(statistics.correlation(xs,ts),result['correlations']['hucking_vs_throws_change']['pearson'],abs_tol=1e-12)
        for stage in [0,1]:
            x=[t['stages'][stage]['hap'] for t in result['teams']]
            y=[t['stages'][stage]['mean_throws'] for t in result['teams']]
            assert math.isclose(statistics.correlation(x,y),result['correlations']['hucking_vs_throws_'+['first','second'][stage]]['pearson'],abs_tol=1e-12)
        assert sum(s['possessions'] for s in result['league']['stages'])==len(subset)
receipt={'passed':True,'group_rates_recomputed_independently':checks,'all_requested_correlations_checked':True,
         'same_cohort_and_original_line_audit_reconciled':True,'input_hashes_current':True,
         'primary_bootstrap_valid_draws':d['scopes']['long_field']['all']['correlations']['hucking_vs_scoring_change']['valid_bootstrap']}
(ROOT/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
