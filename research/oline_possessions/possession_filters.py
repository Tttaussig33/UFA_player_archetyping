"""Build exact first/second/third table views without changing fitted comparisons."""
from pathlib import Path
import csv
import hashlib
import json
import math

import numpy as np
import pandas as pd
import analyze

ROOT = Path(__file__).resolve().parent
METRICS = ['throws_goal', 'throws_turnover', 'scoring', 'early_huck',
           'huck_share', 'any_huck', 'huck_completion', 'break_after_turnover']


def main():
    base = json.loads((ROOT / 'results.json').read_text())
    follow = json.loads((ROOT / 'follow_up_20261106.json').read_text())
    for name in ['possessions.csv', 'throws.csv']:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == base['inputs'][name]
    p = pd.read_csv(ROOT / 'possessions.csv')
    t = pd.read_csv(ROOT / 'throws.csv')
    p = p[~p.has_timeout].copy()
    t = t[~t.has_timeout].copy()
    analyze.RNG = np.random.default_rng(20261109)
    result = {
        'date': '2026-11-09',
        'definition': 'Exact own-team possession number within the receiving point. Third excludes fourth and later. Timeout exclusions never renumber possessions.',
        'scope': 'Same preserved 2026 regular-season cohort, timeout exclusion, metric denominators and huck eligibility as the original analysis.',
        'uncertainty': 'First and second retain the reviewed original intervals. Exact-third intervals resample whole games 10000 times, seed 20261109; intervals are omitted when fewer than two games contribute. No models or significance tests are refitted.',
        'possession_counts': {str(i): int(p.own_possession.eq(i).sum()) for i in [1, 2, 3]},
        'fourth_or_later_not_in_third': int(p.own_possession.gt(3).sum()),
        'teams': []}
    for team in base['teams']:
        tid = team['team']
        pp = p[p.team.eq(tid)]
        tt = t[t.team.eq(tid)]
        datasets = analyze.dataset_metrics(pp, tt)
        turnovers = pp[pp.outcome.eq('turnover') & pp.point_end.eq('goal')].copy()
        turnovers['eventual_break'] = turnovers.point_hold.eq(0).astype(int)
        datasets['break_after_turnover'] = (turnovers, 'eventual_break')
        row = {'team': tid, 'team_name': team['team_name'], 'games': team['games'], 'metrics': {}}
        for key in METRICS:
            d, outcome = datasets[key]
            original = (next(x for x in follow['break_teams'] if x['team'] == tid)
                        if key == 'break_after_turnover' else team['metrics'][key])
            third = analyze.observed(d[d.own_possession.le(3)], outcome,
                                     (1, 2, 3), 'own_possession')['groups'][2]
            third['name'] = 'Third'
            if third['games'] < 2:
                third['ci95'] = None
            row['metrics'][key] = [*original['groups'][:2], third]
        result['teams'].append(row)

    # Reconcile every displayed numerator/denominator independently with CSV rows.
    def read(name):
        with (ROOT / name).open(newline='') as f:
            return [r for r in csv.DictReader(f) if r['has_timeout'] == 'False']
    pp, tt = read('possessions.csv'), read('throws.csv')
    eligible = lambda r: bool(r['first_y']) and float(r['first_y']) <= 60
    records = {
        'throws_goal': ([r for r in pp if r['outcome'] == 'goal'], lambda r: int(r['throws'])),
        'throws_turnover': ([r for r in pp if r['outcome'] == 'turnover'], lambda r: int(r['throws'])),
        'scoring': ([r for r in pp if r['outcome'] in ['goal', 'turnover']], lambda r: int(r['goal'])),
        'early_huck': ([r for r in pp if eligible(r)], lambda r: int(r['early_huck'])),
        'any_huck': ([r for r in pp if eligible(r)], lambda r: int(r['has_huck'])),
        'huck_share': ([r for r in tt if eligible(r)], lambda r: int(r['huck'])),
        'huck_completion': ([r for r in tt if eligible(r) and r['huck'] == '1'], lambda r: int(r['complete'])),
        'break_after_turnover': ([r for r in pp if r['outcome'] == 'turnover' and r['point_end'] == 'goal'], lambda r: int(r['point_hold'] == '0'))}
    checked = 0
    for team in result['teams']:
        for key, groups in team['metrics'].items():
            rows, value = records[key]
            for g in groups:
                subset = [r for r in rows if r['team'] == team['team'] and int(r['own_possession']) == g['stage']]
                assert len(subset) == g['n']
                assert sum(map(value, subset)) == g['sum']
                assert len({r['GameID'] for r in subset}) == g['games']
                if subset:
                    assert math.isclose(sum(map(value, subset)) / len(subset), g['estimate'], abs_tol=1e-12)
                else:
                    assert g['estimate'] is None and g['ci95'] is None
                checked += 1
    result['validation'] = {'passed': True, 'groups_checked': checked,
        'checks': ['All displayed exact-stage counts, sums, means, rates and game counts independently reconciled with CSV.',
                   'First and second estimates and intervals preserved from existing reviewed results.',
                   'Third uses own_possession == 3; fourth and later excluded; original numbers retained after timeout filtering.']}
    result['inputs'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                       for name in ['results.json', 'follow_up_20261106.json', 'possessions.csv', 'throws.csv']}
    analyze.dump('possession_filters.json', result)
    print(json.dumps({k: result[k] for k in ['possession_counts', 'fourth_or_later_not_in_third', 'validation']}, indent=2))


if __name__ == '__main__':
    main()
