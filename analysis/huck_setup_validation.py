"""Does the preceding pass improve later-season huck-attempt forecasts?

Extends the fixed historical player/field baseline; no live database access.
Input: hash-checked October 12 exports, 2021–2026 regular seasons.
Output: reviewed aggregate JSON; no raw CSVs or credentials are written.

Analysis design fixed before inspecting these new results:
* Primary: 2021–2025 train -> 2026 test, Y20 <= release < Y60, >=40
  historical hucks in this window (same eligibility as the earlier study).
* Primary incremental comparison: incoming direction versus a baseline that
  already knows whether an incoming direction can be classified.
* Earlier temporal checks: test 2023, 2024, 2025 using only earlier seasons.
* Sensitivities: >=10 prior hucks; 2024–25 history; known directions only;
  5x5-yard release grid; team adjustment. No hyperparameter tuning on test data.
* Brier error is primary; log loss, calibration and top-20% capture are
  secondary. More detailed and personal setup features are exploratory.
* Viability means consistent later-season gain, not a causal coaching effect.
  This is exploratory temporal validation, not an untouched external test.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

import multiseason_release_validation as history

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIRECTIONS = ['forward', 'lateral', 'backward', 'unclassified']
CONTEXT = ['GameID', 'is_home_team', 'game_quarter', 'quarter_point', 'possession_num']
SEQUENCE = ['game_quarter', 'quarter_point', 'possession_num', 'possession_throw', 'global_event_seq']
BOOL_TRUE = ['1', '1.0', 'true', 'True']


def link_incoming(raw):
    """One-to-one consecutive possession links, with explicit exclusion reasons.

    Uses all source passes before filtering current throwers, release location,
    or huck outcomes. Never links across a game, team, quarter, point or
    possession, and never guesses from nearby coordinates or row order.
    """
    t = raw.copy().reset_index(drop=True)
    t['_row'] = np.arange(len(t))
    for col in SEQUENCE:
        t[col] = pd.to_numeric(t[col], errors='coerce')
    for col in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']:
        t[col] = pd.to_numeric(t[col], errors='coerce')
    valid_context = t.GameID.ne('') & t.is_home_team.isin(['true', 'false'])
    for col in ['game_quarter', 'quarter_point', 'possession_num']:
        valid_context &= t[col].notna() & t[col].ge(0) & t[col].mod(1).eq(0)
    valid_order = t.possession_throw.notna() & t.possession_throw.ge(1) & t.possession_throw.mod(1).eq(0)
    t['reason'] = 'invalid_context'
    t.loc[valid_context, 'reason'] = 'invalid_order'
    t.loc[valid_context & valid_order, 'reason'] = 'first_throw'
    w = t.loc[valid_context & valid_order].copy()
    w['orderCount'] = w.groupby(CONTEXT + ['possession_throw'], dropna=False)._row.transform('size')
    w['sequenceCount'] = w.groupby(CONTEXT + ['global_event_seq'], dropna=False)._row.transform('size')
    previous_cols = ['_row', 'Thrower', 'Receiver', 'ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY',
                     'turnover', 'stall', 'global_event_seq', 'sequenceCount', 'throw_sig_id']
    # A unique lookup prevents multiplication even when source orders are ambiguous.
    p = w.loc[w.orderCount.eq(1), CONTEXT + ['possession_throw'] + previous_cols].copy()
    p['possession_throw'] += 1
    p = p.rename(columns={c: 'prior_' + c for c in previous_cols})
    z = w.merge(p, on=CONTEXT + ['possession_throw'], how='left', validate='many_to_one')
    named = ~z.Thrower.str.lower().isin(['', 'unknown', 'none', 'null', 'nan'])
    conditions = [
        z.possession_throw.lt(2), z.orderCount.ne(1), z.prior__row.isna(),
        ~named | z.prior_Receiver.ne(z.Thrower),
        z.prior_turnover.isin(BOOL_TRUE) | z.prior_stall.isin(BOOL_TRUE),
        ~np.isfinite(z.global_event_seq) | ~np.isfinite(z.prior_global_event_seq),
        z.sequenceCount.ne(1) | z.prior_sequenceCount.ne(1),
        z.prior_global_event_seq.ge(z.global_event_seq),
    ]
    reasons = ['first_throw', 'ambiguous_current_order', 'missing_or_ambiguous_prior_order',
               'receiver_identity_mismatch', 'prior_not_completed_or_stall', 'missing_sequence',
               'ambiguous_sequence', 'nonincreasing_sequence']
    z['reason'] = np.select(conditions, reasons, default='verified')
    z['linkVerified'] = z.reason.eq('verified')
    geometry = np.isfinite(z[['prior_ThrowerX', 'prior_ThrowerY', 'prior_ReceiverX', 'prior_ReceiverY']]).all(axis=1)
    dx = z.prior_ReceiverX - z.prior_ThrowerX
    dy = z.prior_ReceiverY - z.prior_ThrowerY
    z.loc[z.linkVerified & ~geometry, 'reason'] = 'prior_missing_geometry'
    z.loc[z.linkVerified & geometry & dx.eq(0) & dy.eq(0), 'reason'] = 'prior_zero_distance'
    classified = z.reason.eq('verified')
    z['incoming'] = np.select([classified & dy.gt(dx.abs()), classified & (-dy).gt(dx.abs()), classified],
                              ['forward', 'backward', 'lateral'], default='unclassified')
    distance = np.hypot(dx, dy)
    z['incomingDistance'] = np.select([classified & distance.le(10), classified & distance.le(20),
                                      classified & distance.le(40), classified],
                                     ['0–10 yd', '10–20 yd', '20–40 yd', '>40 yd'], default='unclassified')
    z['catchZone'] = history.assign_zones(z.prior_ReceiverX, z.prior_ReceiverY).where(classified, 'unclassified').replace('', 'unclassified')
    fields = ['reason', 'linkVerified', 'incoming', 'incomingDistance', 'catchZone', 'prior_throw_sig_id']
    out = t[['GameID', 'throw_sig_id', 'reason']].copy()
    out['linkVerified'] = False
    for c in ['incoming', 'incomingDistance', 'catchZone']:
        out[c] = 'unclassified'
    out['prior_throw_sig_id'] = ''
    out.loc[z._row, fields] = z[fields].fillna('').to_numpy()
    out['linkVerified'] = out.linkVerified.astype(bool)
    out['incomingKnown'] = np.where(out.incoming.eq('unclassified'), 'unclassified', 'classified')
    assert len(out) == len(raw)
    assert not out[['GameID', 'throw_sig_id']].duplicated().any()
    return out


def load_data():
    d, names, quality, hashes = history.load_data()
    cols = ['GameID', 'throw_sig_id', 'Thrower', 'Receiver', 'ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY',
            'turnover', 'stall', 'is_home_team'] + SEQUENCE
    raw = pd.read_csv(history.EXPORTS / 'throws.csv', usecols=cols, dtype=str, keep_default_na=False)
    linked = link_incoming(raw)
    d = d.merge(linked, left_on=['game', 'throwID'], right_on=['GameID', 'throw_sig_id'],
                how='left', validate='one_to_one')
    assert d.incoming.notna().all()
    d['releaseGrid'] = np.floor((d.tx + 26.67) / 5).astype(int).astype(str) + '|' + np.floor(d.ty / 5).astype(int).astype(str)
    d['cell'] = d.player + '|' + d.incoming
    quality['incomingBySeason'] = []
    for year, rows in d.groupby('season'):
        scope = rows[rows.ty.between(20, 60, inclusive='left')]
        quality['incomingBySeason'].append({
            'season': int(year), 'allAnalysisPasses': len(rows),
            'verifiedLinksAllPositions': int(rows.linkVerified.sum()),
            'windowPasses': len(scope), 'windowHucks': int(scope.huck.sum()),
            'classifiedWindowPasses': int(scope.incoming.ne('unclassified').sum()),
            'classifiedWindowHucks': int((scope.incoming.ne('unclassified') & scope.huck).sum()),
            'reasons': {str(k): int(v) for k, v in scope.reason.value_counts().items()},
        })
    quality['allSourceLinkReasons'] = {str(k): int(v) for k, v in linked.reason.value_counts().items()}
    return d, names, quality, hashes, linked


def calibration(y, pred):
    rows = []
    for low, high in zip([0, .05, .1, .15, .2, .3, .5], [.05, .1, .15, .2, .3, .5, 1.000001]):
        mask = (pred >= low) & (pred < high)
        if mask.any():
            rows.append({'low': low, 'high': min(high, 1), 'passes': int(mask.sum()),
                         'hucks': int(y[mask].sum()), 'prediction': float(pred[mask].mean()),
                         'observed': float(y[mask].mean())})
    return rows


def evaluate(d, test_year, *, first_year=2021, min_hucks=40, known_only=False,
             fine_grid=False, team_adjustment=False, details=False, models=None):
    scope = d[d.ty.between(20, 60, inclusive='left')].copy()
    train = scope[(scope.season >= first_year) & (scope.season < test_year)].copy()
    test = scope[scope.season.eq(test_year)].copy()
    # Eligibility is defined before known-only exclusions and never on test labels.
    historical_hucks = train.groupby('player').huck.sum()
    eligible = set(historical_hucks[historical_hucks >= min_hucks].index)
    test = test[test.player.isin(eligible)].copy()
    if known_only:
        train, test = train[train.incoming.ne('unclassified')], test[test.incoming.ne('unclassified')]
    assert not (set(train.game) & set(test.game))
    assert int(train.season.max()) < test_year
    position = ['releaseGrid'] if fine_grid else ['zone', 'releaseDepth']
    context = ['team'] if team_adjustment else []
    base = ['player'] + position + context
    specs = {
        'leaguePosition': position + context,
        'playerPosition': base,
        'availability': base + ['incomingKnown'],
        'direction': base + ['incoming'],
        'details': base + ['incoming', 'incomingDistance', 'catchZone'],
        'personalDirection': base + ['incoming', 'cell'],
    }
    if models is not None:
        specs = {k: specs[k] for k in models}
    y = test.huck.to_numpy(float)
    predictions, losses, fits = {}, {}, {}
    result = {
        'testSeason': test_year, 'trainingSeasons': sorted(train.season.unique().tolist()),
        'minimumHistoricalHucksInWindow': min_hucks, 'knownOnly': known_only,
        'fineGrid': fine_grid, 'teamAdjustment': team_adjustment,
        'trainPasses': len(train), 'trainHucks': int(train.huck.sum()),
        'eligibleHistoricalPlayers': len(eligible), 'testPlayers': test.player.nunique(),
        'testGames': test.game.nunique(), 'testPasses': len(test), 'testHucks': int(y.sum()),
        'testRate': float(y.mean()), 'models': {}, 'comparisons': {},
        'incomingRates': [],
    }
    # Stable ID tie-break; no outcome information is used to choose the top fifth.
    tie_order = np.argsort((test.game + ':' + test.throwID).to_numpy(), kind='stable')
    for label, features in specs.items():
        fit = history.AdditiveLogistic(features).fit(train, 'huck')
        pred = fit.predict(test)
        predictions[label], losses[label], fits[label] = pred, (pred - y)**2, fit
        ranking = tie_order[np.argsort(-pred[tie_order], kind='stable')]
        top = ranking[:int(np.ceil(.2 * len(test)))]; top_hucks = int(y[top].sum())
        result['models'][label] = {
            'features': features, 'brier': float(losses[label].mean()),
            'logLoss': float(-(y*np.log(pred) + (1-y)*np.log1p(-pred)).mean()),
            'meanPrediction': float(pred.mean()), 'iterations': fit.iterations,
            'maxParameterChange': fit.max_delta, 'calibration': calibration(y, pred),
            'topFifth': {'passes': len(top), 'hucks': top_hucks, 'huckRate': float(y[top].mean()),
                         'shareOfAllHucks': float(top_hucks / y.sum())},
        }
    pairs = [('playerPosition', 'leaguePosition'), ('availability', 'playerPosition'),
             ('direction', 'playerPosition'), ('direction', 'availability'),
             ('details', 'direction'), ('personalDirection', 'direction')]
    for extended, base_label in pairs:
        if extended not in losses or base_label not in losses:
            continue
        improvement = losses[base_label] - losses[extended]
        denominator = float(losses[base_label].mean())
        result['comparisons'][extended + 'Vs' + base_label[0].upper() + base_label[1:]] = {
            'base': base_label, 'extended': extended, 'brierReduction': float(improvement.mean()),
            'relativeErrorReductionPct': float(100 * improvement.mean() / denominator),
            'gameBootstrap': history.cluster_ci(improvement, test.game.to_numpy()),
            'playerBootstrap': history.cluster_ci(improvement, test.player.to_numpy()),
            'logLossReduction': result['models'][base_label]['logLoss'] - result['models'][extended]['logLoss'],
        }
    for setup in DIRECTIONS:
        subset = test[test.incoming.eq(setup)]
        result['incomingRates'].append({'direction': setup, 'passes': len(subset),
                                       'hucks': int(subset.huck.sum()),
                                       'huckRate': float(subset.huck.mean()) if len(subset) else None})
    if details:
        result['players'] = []
        for player in sorted(test.player.unique()):
            mask = test.player.eq(player).to_numpy(); s = test.loc[mask]
            row = {'player': player, 'passes': int(mask.sum()), 'hucks': int(y[mask].sum()),
                   'historicalHucksInWindow': int(historical_hucks[player]),
                   'directions': [{'direction': k, 'passes': len(g), 'hucks': int(g.huck.sum())}
                                  for k,g in s.groupby('incoming')],
                   'brier': {k: float(v[mask].mean()) for k,v in losses.items()}}
            result['players'].append(row)
        result['coefficients'] = {label: {feature: {str(k): float(fit.betas[feature][idx])
            for k,idx in fit.maps[feature].items()} for feature in fit.features if feature != 'player' and feature != 'cell'}
            for label,fit in fits.items()}
    return result


def run():
    d, names, quality, hashes, linked = load_data()
    print('Hashed inputs and conservative incoming-pass joins verified.', flush=True)
    studies = []
    for year in [2023, 2024, 2025, 2026]:
        result = evaluate(d, year, details=year == 2026)
        studies.append(result)
        c = result['comparisons']['directionVsAvailability']
        print(json.dumps({'testSeason': year, 'passes': result['testPasses'], 'hucks': result['testHucks'],
                          'directionBeyondAvailability': c}), flush=True)
    sensitivities = {}
    for name,kwargs in {
        'lowerHistoricalFloor': {'min_hucks': 10},
        'recentHistory': {'first_year': 2024},
        'knownDirectionsOnly': {'known_only': True},
        'finerReleasePosition': {'fine_grid': True},
        'teamAdjustment': {'team_adjustment': True},
    }.items():
        print('Sensitivity: ' + name, flush=True)
        sensitivities[name] = evaluate(d, 2026, models=['playerPosition', 'availability', 'direction'], **kwargs)
    # Match the earlier baseline exactly, so a changed population cannot explain an improvement.
    old = json.loads((HERE / 'multiseason_release_validation.json').read_text())
    prior = old['studies'][-1]['attemptPredictionY20_60']
    new = studies[-1]
    assert (new['testPasses'], new['testHucks'], new['testPlayers']) == (prior['testEvents'], prior['testSuccesses'], prior['testPlayers'])
    assert abs(new['models']['playerPosition']['brier'] - prior['models']['sharedGeometry']['brier']) < 1e-12
    result = {
        'question': 'Does the preceding pass add useful information for forecasting a deep throw beyond player history and release position?',
        'source': {'snapshot': '2026-10-12', 'tables': ['prod.throws', 'prod.games', 'prod.players'],
                   'sha256': hashes, 'liveCountsCheckedOn': '2026-10-24',
                   'freshness': 'Original exported rows; matching live counts do not establish current row identity.'},
        'method': {
            'unit': 'A located, non-stall pass by a named thrower, released at Y20 <= Y < 60 in a regular-season game.',
            'target': 'Huck = receiverY - throwerY > 30 and Euclidean endpoint distance > 40 yards; outcomes include incomplete throws.',
            'link': 'Same game, team side, quarter, point and possession; consecutive unique throw orders; unique increasing event sequences; prior completed non-stall pass with receiver equal to current thrower.',
            'incomingDirection': 'forward: dy > abs(dx); backward: -dy > abs(dx); lateral otherwise for a finite nonzero prior vector. Missing/zero or unverifiable setups stay unclassified.',
            'primaryComparison': 'direction vs availability on 2026 events, trained only on 2021–2025.',
            'eligibility': 'At least 40 prior hucks in Y20–60, defined from historical labels only; 10-huck sensitivity.',
            'penalties': 'Fixed L2 log-odds penalties: player 2.5; player-by-incoming interaction 5; other categorical features 1; intercept unpenalized.',
            'selection': 'Primary comparison, seasons, models, thresholds and sensitivities fixed in the script before viewing the new result. Previously inspected 2026 makes this exploratory.',
            'uncertainty': '5000 paired bootstrap draws of whole games and separately whole players. Conditional on fitted training models; neither interval captures all crossed dependence or model-selection uncertainty.',
            'positiveImprovement': 'Lower Brier error. Relative reduction is loss difference divided by baseline loss; it is not a change in completion percentage.',
            'topFifth': 'Rank all held-out passes by predicted huck probability with stable ID tie-break, select ceil(20% of passes). Descriptive ranking check, not a deployed coaching threshold.',
            'limitations': ['Directions describe disc movement, not upline/swing cutting routes or dead-disc state.',
                           'No receiver positioning at release, mark, pressure, wind or stall count.',
                           'Release coordinates are current throw origins; a forecast made at the instant of catching may have different information.',
                           'Only recorded next throws are outcomes: catches with no subsequent recorded throw are outside this denominator.',
                           'Regular seasons and returning high-volume huckers only in the primary cohort; no causal defensive claim.',
                           'Temporal checks share training years and players, so they are not independent replications.'],
        },
        'quality': quality, 'names': names, 'studies': studies, 'sensitivities': sensitivities,
        'baselineReconciliation': {'passes': new['testPasses'], 'hucks': new['testHucks'], 'players': new['testPlayers'],
                                   'brierDifferenceFromPriorStudy': new['models']['playerPosition']['brier'] - prior['models']['sharedGeometry']['brier']},
    }
    (HERE / 'huck_setup_validation.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    run()
