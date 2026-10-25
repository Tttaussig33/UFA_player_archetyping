"""Exploratory temporal validation of release-zone huck findings, 2026 snapshot.

Run from any directory with Python + numpy and Node:
  python3 analysis/release_zone_validation.py --node /absolute/path/to/node
All source data is read-only. June 15 is the primary chronological split.
June 22 and July 1 are sensitivity analyses, not independent replications.
No model parameters are selected on held-out outcomes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shutil
import subprocess
import numpy as np

HERE = Path(__file__).resolve().parent
SEED = 20261022


def counts(rows, outcome='complete'):
    n = len(rows)
    successes = sum(int(r[outcome]) for r in rows)
    return {'attempts': n, 'successes': successes, 'rate': successes / n if n else None}


def grouped(rows, keys):
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keys)].append(r)
    return groups


def mean_ci(values, seed=SEED):
    """Equal-player mean; resample whole players, conditional on early selection."""
    if not values:
        return None
    v = np.array(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(10000, len(v)))].mean(axis=1)
    return {'mean': float(v.mean()), 'ci95': [float(x) for x in np.quantile(means, [.025, .975])], 'players': len(v)}


def clustered_loss_ci(rows, differences):
    """Paired, throw-weighted loss difference; resample whole held-out games."""
    groups = defaultdict(list)
    for r, d in zip(rows, differences):
        groups[r['game']].append(d)
    sums = np.array([sum(x) for x in groups.values()])
    ns = np.array([len(x) for x in groups.values()])
    if not len(ns):
        return None
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(ns), size=(10000, len(ns)))
    means = sums[draws].sum(axis=1) / ns[draws].sum(axis=1)
    return {'mean': float(np.mean(differences)),
            'ci95': [float(x) for x in np.quantile(means, [.025, .975])], 'games': len(ns)}


def best_zone_test(train, test, names, outcome='complete', zone_min=5, min_hucks=10):
    tp = grouped(train, ['player']); vp = grouped(test, ['player'])
    rows = []
    for (player,), early in sorted(tp.items()):
        if sum(r['huck'] for r in early) < min_hucks:
            continue
        zones = grouped(early, ['zone'])
        eligible = [(z, rs) for (z,), rs in zones.items()
                    if z is not None and len(rs) >= zone_min
                    and (outcome != 'huck' or sum(r['huck'] for r in rs) >= 3)]
        if len(eligible) < 2:
            continue
        eligible.sort(key=lambda v: (-counts(v[1], outcome)['rate'], -len(v[1]), v[0]))
        best, _ = eligible[0]
        later = vp[(player,)]
        row = {'player': player, 'name': names.get(player, player), 'zone': best,
               'eligibleEarlyZones': len(eligible)}
        for period, rs in [('early', early), ('later', later)]:
            row[period] = {'chosen': counts([r for r in rs if r['zone'] == best], outcome),
                           'other': counts([r for r in rs if r['zone'] != best], outcome)}
            a, b = row[period]['chosen']['rate'], row[period]['other']['rate']
            row[period]['difference'] = a-b if a is not None and b is not None else None
        rows.append(row)
    paired = [r for r in rows if r['later']['difference'] is not None]
    return {'eligiblePlayers': len(rows), 'evaluatedPlayers': len(paired),
            'earlyAdvantage': mean_ci([r['early']['difference'] for r in paired]),
            'laterAdvantage': mean_ci([r['later']['difference'] for r in paired]),
            'laterPositive': sum(r['later']['difference'] > 0 for r in paired),
            'laterZero': sum(r['later']['difference'] == 0 for r in paired),
            'earlyChosen': combine_counts([r['early']['chosen'] for r in paired]),
            'earlyOther': combine_counts([r['early']['other'] for r in paired]),
            'laterChosen': combine_counts([r['later']['chosen'] for r in paired]),
            'laterOther': combine_counts([r['later']['other'] for r in paired]),
            'rows': rows}


def combine_counts(cs):
    n, y = sum(r['attempts'] for r in cs), sum(r['successes'] for r in cs)
    return {'attempts': n, 'successes': y, 'rate': y/n if n else None}


def clipped_logit(p):
    p = min(.999, max(.001, p))
    return math.log(p/(1-p))


def sigmoid(x):
    return 1/(1+math.exp(-x))


def predictive_test(train, test, outcome='complete', prior_n=20):
    """Fixed empirical-Bayes baselines, no hyperparameter search on test data.

    Base: player rate with 10 league-rate pseudo-attempts.
    Shared zone: add smoothed league-zone log-odds offset to base log-odds.
    Personal zone: observed cell with prior_n shared-zone pseudo-attempts.
    Includes only players with >=10 early hucks, chosen without late outcomes.
    """
    tp = grouped(train, ['player']); tz = grouped(train, ['zone'])
    tpz = grouped(train, ['player', 'zone'])
    baseline = counts(train, outcome)['rate']
    eligible = {p for (p,), rs in tp.items() if sum(r['huck'] for r in rs) >= 10}
    test = [r for r in test if r['player'] in eligible]
    predictions = {k: [] for k in ['player', 'sharedZone', 'personalZone']}
    for r in test:
        p, z = r['player'], r['zone']
        s, zs, pzs = [counts(x, outcome) for x in [tp[(p,)], tz[(z,)], tpz[(p,z)]]]
        pp = (s['successes']+10*baseline)/(s['attempts']+10)
        zp = (zs['successes']+20*baseline)/(zs['attempts']+20)
        shared = sigmoid(clipped_logit(pp)+clipped_logit(zp)-clipped_logit(baseline))
        personal = (pzs['successes']+prior_n*shared)/(pzs['attempts']+prior_n)
        for k, pred in [('player', pp), ('sharedZone', shared), ('personalZone', personal)]:
            predictions[k].append(pred)
    y = np.array([r[outcome] for r in test], dtype=float)
    losses = {k: (np.array(v)-y)**2 for k,v in predictions.items()}
    return {'eligiblePlayers': len(eligible), 'evaluatedPlayers': len({r['player'] for r in test}),
            'testEvents': len(test), 'testSuccesses': int(y.sum()),
            'brier': {k: float(v.mean()) for k,v in losses.items()},
            'sharedMinusPlayer': clustered_loss_ci(test, losses['sharedZone']-losses['player']),
            'personalMinusShared': clustered_loss_ci(test, losses['personalZone']-losses['sharedZone']),
            'personalMinusPlayer': clustered_loss_ci(test, losses['personalZone']-losses['player']),
            'cellPriorAttempts': prior_n}


def split_study(rows, names, cutoff):
    early = [r for r in rows if r['date'] < cutoff]
    later = [r for r in rows if r['date'] >= cutoff]
    eh, lh = [[r for r in rs if r['huck']] for rs in [early,later]]
    # Entire games are kept together and every test date is later.
    assert not ({r['game'] for r in early} & {r['game'] for r in later})
    return {'cutoff': cutoff, 'earlyThrows': len(early), 'laterThrows': len(later),
            'earlyHucks': counts(eh), 'laterHucks': counts(lh),
            'bestSuccessZone': best_zone_test(eh,lh,names),
            'successPrediction': predictive_test(eh,lh),
            'bestChoiceZone': best_zone_test(early,later,names,'huck',20),
            'choicePrediction': predictive_test(early,later,'huck'),
            'priorSensitivity': {str(n): predictive_test(eh,lh,prior_n=n) for n in [5,10,40]}}


def run(node):
    prepared = json.loads(subprocess.check_output([node,str(HERE/'release_zone_inputs.mjs')]))
    rows = prepared['rows']
    names = {p['id']:p['name'] for p in prepared['players']}
    assert len({r['id'] for r in rows}) == len(rows), 'Duplicate source events'
    for r in rows:
        endpoints=[r[k] for k in ['tx','ty','rx','ry']]
        finite=all(isinstance(v,(float,int)) and math.isfinite(v) for v in endpoints)
        independently_huck=finite and r['ry']-r['ty']>30 and math.hypot(r['rx']-r['tx'],r['ry']-r['ty'])>40
        assert r['huck'] == independently_huck, r['id']
    located=[r for r in rows if r['distance'] is not None and r['zone'] is not None]
    hucks=[r for r in located if r['huck']]
    studies=[split_study(located,names,cut) for cut in ['2026-06-15','2026-06-22','2026-07-01']]
    # Exploratory sensitivity: do not mistake the geometry of being near the
    # scoring end zone for a useful, individual deep-throwing archetype.
    spatial_sensitivity=[]
    for label, predicate in [('release_before_y80',lambda r:r['ty']<80),
                             ('release_y20_60',lambda r:20<=r['ty']<60)]:
        rs=[r for r in located if predicate(r)]
        t=[r for r in rs if r['date']<'2026-06-15']
        v=[r for r in rs if r['date']>='2026-06-15']
        spatial_sensitivity.append({'scope':label,'choicePrediction':predictive_test(t,v,'huck'),
                                    'bestChoiceZone':best_zone_test(t,v,names,'huck',20)})
    cp_finite=[r for r in hucks if isinstance(r['cp'],(float,int)) and math.isfinite(r['cp'])]
    cp_check={'count':len(cp_finite),'meanExpected':float(np.mean([r['cp'] for r in cp_finite])),
              'observed':counts(cp_finite),
              'cpoeNotEqualOutcomeMinusCp':sum(abs(r['cpoe']-(r['complete']-r['cp']))>1e-8 for r in cp_finite),
              'drops':sum(r['drop'] for r in cp_finite)}
    distance_bands=[]
    for low,high in [(40,50),(50,60),(60,70),(70,math.inf)]:
        rs=[r for r in hucks if low<r['distance']<=high]
        distance_bands.append({'lowerExclusive':low,'upperInclusive':high if math.isfinite(high) else None,**counts(rs)})
    selected={r['player']:r['zone'] for r in studies[0]['bestSuccessZone']['rows']
              if r['later']['difference'] is not None}
    difficulty_comparison=[]
    for period, predicate in [('early',lambda r:r['date']<'2026-06-15'),
                               ('later',lambda r:r['date']>='2026-06-15')]:
        for chosen in [True,False]:
            rs=[r for r in hucks if predicate(r) and r['player'] in selected
                and (r['zone']==selected[r['player']])==chosen]
            difficulty_comparison.append({'period':period,'chosen':chosen,**counts(rs),
                'meanDistance':float(np.mean([r['distance'] for r in rs])),
                'meanSuppliedCp':float(np.mean([r['cp'] for r in rs])),
                'meanOutcomeMinusCp':float(np.mean([r['complete']-r['cp'] for r in rs]))})
    zones=[]
    for z in prepared['zones']:
        rs=[r for r in hucks if r['zone']==z['id']]
        if not rs: continue
        zones.append({**z,**counts(rs),'distanceMean':float(np.mean([r['distance'] for r in rs])),
                      'expectedMean':float(np.mean([r['cp'] for r in rs])),
                      'players':len({r['player'] for r in rs})})
    result={'source':prepared['source'],
            'method':{'primaryCutoff':'2026-06-15','phase':'Regular season','huck':'Forward gain >30 AND Euclidean distance >40 yards; stalls excluded.',
                      'bestZone':'At least 5 early hucks in at least 2 zones; pick highest rate, ties by attempt count then zone ID. Later comparison is chosen zone versus all other zones for the same player.',
                      'choiceZone':'At least 10 early hucks; at least 2 zones each with 20 located throws and 3 hucks; choose highest early huck/throw rate.',
                      'uncertainty':'10,000 bootstrap resamples; best-zone gaps resample players equally; prediction loss differences resample whole games, throw-weighted. Conditional on early selection; does not remove all player dependence or opponent confounding.',
                      'prediction':'Fixed smoothed player baseline, shared zone log-odds adjustment, then player-zone cell shrunk with 20 prior observations toward shared-zone prediction. Smaller Brier error is better. No parameter fitting on later outcomes.',
                      'limitations':['Exploratory analysis of a previously viewed 2026 season, not preregistered or an untouched external validation set.','One season; games within this season may share opponents and conditions.','A zone association is not a causal effect of moving the thrower.','Completion models do not fully adjust for receiver movement, pressure, matchup, weather or throw difficulty.','Alternative choice analysis is exploratory, tested on the same chronological split.']},
            'coverage':{'namedNonstallThrows':len(rows),'locatedMappedThrows':len(located),'hucks':counts(hucks),
                        'missingGeometry':sum(r['distance'] is None for r in rows),
                        'unmappedReleaseWithGeometry':sum(r['distance'] is not None and r['zone'] is None for r in rows),
                        'games':len({r['game'] for r in located}),'start':min(r['date'] for r in rows),'end':max(r['date'] for r in rows)},
            'cpAudit':cp_check,'distanceBands':distance_bands,
            'difficultyComparison':difficulty_comparison,'spatialSensitivity':spatial_sensitivity,
            'zones':zones,'studies':studies}
    (HERE/'release_zone_validation.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--node',default=shutil.which('node'))
    args=parser.parse_args()
    if not args.node: parser.error('Pass --node /absolute/path/to/node')
    result=run(args.node)
    print(json.dumps({**{k:result[k] for k in ['coverage','cpAudit']},
      'studies':[{k:({kk:vv for kk,vv in v.items() if kk!='rows'} if k in ['bestSuccessZone','bestChoiceZone'] else v)
                 for k,v in s.items() if k!='priorSensitivity'} for s in result['studies']]},indent=2))
