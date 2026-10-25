"""Historical, chronological validation of player release-zone tendencies.

Read-only inputs: the checked October 12 exports. Writes an analysis JSON only.
Run with Python, numpy and pandas. No database credentials or network required.
The 2026 results have been viewed before: this is exploratory temporal validation,
not a preregistered experiment or an untouched external validation set.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPORTS = ROOT / 'data/database-exports/2026-10-12'
SEED = 20261024
BOOTSTRAPS = 5000
ZONES = {
    'own-endzone': 'Own end zone',
    'left-build': 'Left sideline, 20–60 yd',
    'right-build': 'Right sideline, 20–60 yd',
    'center-init': 'Center, 20–40 yd',
    'center-build': 'Center, 40–60 yd',
    'left-attack': 'Left sideline, 60–100 yd',
    'right-attack': 'Right sideline, 60–100 yd',
    'center-attack': 'Center, 60–80 yd',
    'center-red': 'Center, 80–100 yd',
    'ez-left': 'Scoring end zone, left',
    'ez-right': 'Scoring end zone, right',
    'ez-deep': 'Scoring end zone, deep',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def assign_zones(x, y):
    valid = x.between(-26.67000001, 26.67000001) & y.between(0, 120)
    zone = pd.Series('', index=x.index, dtype='object')
    zone.loc[y < 20] = 'own-endzone'
    zone.loc[(y >= 20) & (y < 60) & (x < -15)] = 'left-build'
    zone.loc[(y >= 20) & (y < 60) & (x >= 15)] = 'right-build'
    center = (x >= -15) & (x < 15)
    for low, high, name in [(20, 40, 'center-init'), (40, 60, 'center-build'),
                            (60, 80, 'center-attack'), (80, 100, 'center-red')]:
        zone.loc[(y >= low) & (y < high) & center] = name
    zone.loc[(y >= 60) & (y < 100) & (x < -15)] = 'left-attack'
    zone.loc[(y >= 60) & (y < 100) & (x >= 15)] = 'right-attack'
    zone.loc[(y >= 100) & (y < 110) & (x < 0)] = 'ez-left'
    zone.loc[(y >= 100) & (y < 110) & (x >= 0)] = 'ez-right'
    zone.loc[(y >= 110) & (y <= 120)] = 'ez-deep'
    return zone.where(valid, '')


def load_data():
    manifest = json.loads((EXPORTS / 'manifest.json').read_text())
    source_hashes = {}
    for table in ['throws', 'games', 'players']:
        source_hashes[table] = digest(EXPORTS / f'{table}.csv')
        assert source_hashes[table] == manifest['tables'][table]['sha256'], table
    g = pd.read_csv(EXPORTS / 'games.csv', dtype=str, keep_default_na=False)
    p = pd.read_csv(EXPORTS / 'players.csv', dtype=str, keep_default_na=False)
    columns = ['GameID', 'Thrower', 'ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY',
               'turnover', 'stall', 'DroppedThrow', 'throw_sig_id', 'is_home_team',
               'source_event_type', 'x_diff', 'y_diff', 'throw_distance']
    t = pd.read_csv(EXPORTS / 'throws.csv', usecols=columns, dtype=str, keep_default_na=False)
    assert not g.GameID.duplicated().any()
    assert not t[['GameID', 'throw_sig_id']].duplicated().any()
    assert not (t.throw_sig_id == '').any()
    t = t.merge(g[['GameID', 'Year', 'RegularSeasonWeek', 'PlayoffRound', 'HomeTeamID', 'AwayTeamID']],
                on='GameID', how='left', validate='many_to_one', indicator=True)
    assert (t._merge == 'both').all()
    t['season'] = pd.to_numeric(t.Year).astype(int)
    assert ((g.RegularSeasonWeek != '') & (g.PlayoffRound != '')).sum() == 0
    t['phase'] = np.select([t.RegularSeasonWeek != '', t.PlayoffRound != ''],
                           ['regular', 'playoffs'], default='unclassified')
    for old, new in [('ThrowerX', 'tx'), ('ThrowerY', 'ty'), ('ReceiverX', 'rx'), ('ReceiverY', 'ry')]:
        t[new] = pd.to_numeric(t[old], errors='coerce')
    t['distance'] = np.hypot(t.rx - t.tx, t.ry - t.ty)
    t['gain'] = t.ry - t.ty
    t['stallFlag'] = t.stall.isin(['1', '1.0', 'true', 'True'])
    t['complete'] = ~t.turnover.isin(['1', '1.0', 'true', 'True'])
    t['huck'] = (t.gain > 30) & (t.distance > 40) & ~t.stallFlag
    t['zone'] = assign_zones(t.tx, t.ty)
    t['player'] = t.Thrower
    t['game'] = t.GameID
    t['team'] = np.where(t.is_home_team.str.lower() == 'true', t.HomeTeamID, t.AwayTeamID)
    assert p.groupby('PlayerID').full_name.nunique().max() == 1
    names = p.drop_duplicates('PlayerID').set_index('PlayerID').full_name.to_dict()
    named = ~t.player.str.lower().isin(['', 'unknown', 'none', 'null', 'nan'])
    finite = np.isfinite(t[['tx', 'ty', 'rx', 'ry']]).all(axis=1)
    valid = finite & t.zone.ne('') & t.rx.between(-26.67000001, 26.67000001) & t.ry.between(0, 120)
    use = t.season.between(2021, 2026) & (t.phase == 'regular') & named & ~t.stallFlag & valid
    quality = {
        'rows': len(t), 'uniqueGameThrowIDs': len(t), 'duplicateGameIDs': 0, 'orphanThrows': 0,
        'missingCoordinatesAllPhases': int((~finite).sum()),
        'phaseUnclassifiedThrows': int((t.phase == 'unclassified').sum()),
        'unclassifiedGamesWithThrows': sorted(t.loc[t.phase == 'unclassified', 'game'].unique()),
        'ambiguousNamesNotMerged': p.groupby('full_name').PlayerID.nunique().loc[lambda s: s > 1].to_dict(),
        'geometryMismatches': {}, 'seasonRows': [],
    }
    for source, actual in [('x_diff', t.rx - t.tx), ('y_diff', t.gain), ('throw_distance', t.distance)]:
        supplied = pd.to_numeric(t[source], errors='coerce')
        comparable = supplied.notna() & actual.notna()
        quality['geometryMismatches'][source] = {
            'compared': int(comparable.sum()),
            'mismatchesBeyond1e6': int(((supplied - actual).abs()[comparable] > 1e-6).sum()),
        }
    live = json.loads((ROOT / 'data/database-metadata/2026-10-24/live-season-coverage.json').read_text())
    for row in live['rows']:
        local = t[t.season == row['season']]
        assert len(local) == row['throws']
        assert local.game.nunique() == row['games_with_throws']
        assert int((g.Year == str(row['season'])).sum()) == row['listed_games']
    # Keep the live receipt separate: matching row counts is not content identity.
    quality['liveReceipt'] = 'data/database-metadata/2026-10-24/live-season-coverage.json'
    for season, s in t.groupby('season'):
        regular = s.phase == 'regular'
        kept = t.loc[s.index].loc[use.loc[s.index]]
        quality['seasonRows'].append({
            'season': int(season), 'allThrows': len(s), 'allGamesWithThrows': s.game.nunique(),
            'regularThrows': int(regular.sum()),
            'excludedUnnamedRegular': int((regular & ~named.loc[s.index]).sum()),
            'excludedStallsRegularNamed': int((regular & named.loc[s.index] & s.stallFlag).sum()),
            'excludedInvalidGeometryRegularNamedNonstall': int((regular & named.loc[s.index] & ~s.stallFlag & ~valid.loc[s.index]).sum()),
            'analysisThrows': len(kept), 'analysisGames': kept.game.nunique(),
            'hucks': int(kept.huck.sum()), 'completedHucks': int((kept.huck & kept.complete).sum()),
        })
    d = t.loc[use, ['season', 'game', 'player', 'team', 'zone', 'complete', 'huck', 'distance', 'gain', 'tx', 'ty', 'rx', 'ry']].copy()
    d['cell'] = d.player + '|' + d.zone
    d['distanceBand'] = pd.cut(d.distance, [0, 40, 50, 60, 70, 80, np.inf], right=True).astype(str)
    d['gainBand'] = pd.cut(d.gain, [-np.inf, 30, 40, 50, 60, 70, np.inf], right=True).astype(str)
    d['targetEndzone'] = (d.ry >= 100).astype(str)
    d['releaseDepth'] = np.floor(d.ty / 10).astype(int).astype(str)
    return d.reset_index(drop=True), names, quality, source_hashes


def count(n, y):
    return {'attempts': int(n), 'successes': int(y), 'rate': float(y / n) if n else None}


def boot_mean(values):
    if not len(values):
        return None
    v = np.asarray(values, dtype=float)
    if len(v) < 10:
        return {'mean': float(v.mean()), 'ci95': None, 'players': len(v),
                'intervalOmitted': 'Fewer than 10 players; bootstrap interval too unstable to present.'}
    rng = np.random.default_rng(SEED)
    b = v[rng.integers(0, len(v), (BOOTSTRAPS, len(v)))].mean(axis=1)
    return {'mean': float(v.mean()), 'ci95': np.quantile(b, [.025, .975]).tolist(), 'players': len(v)}


def cluster_ci(values, labels):
    f = pd.DataFrame({'value': values, 'label': labels}).groupby('label').value.agg(['sum', 'count'])
    sums, ns = f['sum'].to_numpy(), f['count'].to_numpy()
    if len(ns) < 10:
        return {'mean': float(np.mean(values)), 'ci95': None, 'clusters': len(ns),
                'intervalOmitted': 'Fewer than 10 clusters; bootstrap interval too unstable to present.'}
    rng = np.random.default_rng(SEED)
    # Chunk draws to keep player-cluster bootstraps within a small memory budget.
    draws = []
    for start in range(0, BOOTSTRAPS, 500):
        ix = rng.integers(0, len(ns), (min(500, BOOTSTRAPS - start), len(ns)))
        draws.append(sums[ix].sum(axis=1) / ns[ix].sum(axis=1))
    return {'mean': float(np.mean(values)), 'ci95': np.quantile(np.concatenate(draws), [.025, .975]).tolist(), 'clusters': len(ns)}


def best_zone(train, test, names, outcome='complete', zone_min=10, min_hucks=40):
    eligibility = train.groupby('player').huck.sum()
    eligible = set(eligibility[eligibility >= min_hucks].index)
    tab = train[train.player.isin(eligible)].groupby(['player', 'zone'])[outcome].agg(['size', 'sum'])
    choices = []
    for player, rows in tab.groupby(level=0):
        rows = rows[rows['size'] >= zone_min].copy()
        if outcome == 'huck':
            rows = rows[rows['sum'] >= 5]
        if len(rows) < 2:
            continue
        rows['rate'] = rows['sum'] / rows['size']
        rows['zoneID'] = rows.index.get_level_values('zone')
        rows = rows.sort_values(['rate', 'size', 'zoneID'], ascending=[False, False, True])
        choices.append((player, rows.index[0][1]))
    results = []
    tp = {k: v for k, v in train.groupby('player')}
    vp = {k: v for k, v in test.groupby('player')}
    empty = test.iloc[:0]
    for player, zone in choices:
        row = {'player': player, 'name': names.get(player, player), 'zone': zone, 'zoneLabel': ZONES[zone]}
        for period, d in [('train', tp[player]), ('test', vp.get(player, empty))]:
            a, b = d[d.zone == zone], d[d.zone != zone]
            row[period] = {'chosen': count(len(a), a[outcome].sum()), 'other': count(len(b), b[outcome].sum())}
            row[period]['gap'] = float(a[outcome].mean() - b[outcome].mean()) if len(a) and len(b) else None
        results.append(row)
    paired = [r for r in results if r['test']['gap'] is not None]
    summary = {'eligiblePlayers': len(results), 'testablePlayers': len(paired),
               'testPositive': sum(r['test']['gap'] > 0 for r in paired),
               'testTied': sum(r['test']['gap'] == 0 for r in paired),
               'trainPlayerGap': boot_mean([r['train']['gap'] for r in paired]),
               'testPlayerGap': boot_mean([r['test']['gap'] for r in paired]),
               'rows': results}
    for period in ['train', 'test']:
        summary[period] = {}
        for group in ['chosen', 'other']:
            cells = [r[period][group] for r in paired]
            summary[period][group] = count(sum(c['attempts'] for c in cells), sum(c['successes'] for c in cells))
    return summary


class AdditiveLogistic:
    """Penalized binomial model fitted on exact aggregated sufficient statistics.

    Independent zero-centered log-odds penalties; intercept unpenalized.
    Player lambda=2.5, shared features lambda=1, personal cell lambda=5.
    These fixed penalties are not optimized on held-out seasons. At p=.5,
    a cell penalty of 5 is roughly the curvature of 20 prior observations.
    Block Newton updates are exact within disjoint levels of each factor.
    """
    def __init__(self, features):
        self.features = features

    @staticmethod
    def sigmoid(x):
        return 1 / (1 + np.exp(-np.clip(x, -30, 30)))

    def fit(self, frame, outcome):
        a = frame.groupby(self.features, observed=True)[outcome].agg(['sum', 'size']).reset_index()
        successes, n = a['sum'].to_numpy(float), a['size'].to_numpy(float)
        self.maps, self.betas, codes = {}, {}, {}
        for feature in self.features:
            labels = sorted(a[feature].unique())
            self.maps[feature] = {v: i for i, v in enumerate(labels)}
            codes[feature] = a[feature].map(self.maps[feature]).to_numpy(int)
            self.betas[feature] = np.zeros(len(labels))
        rate = successes.sum() / n.sum()
        self.intercept = float(np.log(rate / (1 - rate)))
        eta = np.full(len(a), self.intercept)
        for iteration in range(5000):
            prob = self.sigmoid(eta)
            delta = np.clip((successes - n * prob).sum() / (n * prob * (1 - prob)).sum(), -1, 1)
            self.intercept += delta
            eta += delta
            max_delta = abs(delta)
            for feature in self.features:
                idx, beta = codes[feature], self.betas[feature]
                penalty = 2.5 if feature == 'player' else 5.0 if feature == 'cell' else 1.0
                prob = self.sigmoid(eta)
                gradient = np.bincount(idx, weights=successes - n * prob, minlength=len(beta)) - penalty * beta
                hessian = np.bincount(idx, weights=n * prob * (1 - prob), minlength=len(beta)) + penalty
                delta = np.clip(gradient / hessian, -1, 1)
                beta += delta
                eta += delta[idx]
                max_delta = max(max_delta, float(np.max(np.abs(delta))))
                # Optimize the otherwise redundant feature/intercept shift.
                # This leaves fitted logits unchanged and minimizes the penalty
                # along that direction, substantially accelerating convergence.
                center = float(beta.mean())
                beta -= center
                self.intercept += center
            if max_delta < 1e-7:
                break
        self.iterations = iteration + 1
        self.max_delta = float(max_delta)
        assert max_delta < 1e-5, ('Model convergence', self.features, max_delta)
        return self

    def predict(self, frame):
        eta = np.full(len(frame), self.intercept)
        for feature in self.features:
            indices = frame[feature].map(self.maps[feature]).fillna(-1).to_numpy(int)
            known = indices >= 0
            eta[known] += self.betas[feature][indices[known]]
        return self.sigmoid(eta)


def prediction_test(train, test, outcome='complete', detail=True, min_hucks=40):
    past_hucks = train.groupby('player').huck.sum()
    eligible = set(past_hucks[past_hucks >= min_hucks].index)
    test = test[test.player.isin(eligible)].copy()
    geometry = ['distanceBand', 'gainBand', 'targetEndzone'] if outcome == 'complete' else ['releaseDepth']
    specs = {'leagueGeometry': ['zone'] + geometry,
             'player': ['player'], 'sharedZone': ['player', 'zone'],
             'personalZone': ['player', 'zone', 'cell'],
             'sharedGeometry': ['player', 'zone'] + geometry,
             'personalGeometry': ['player', 'zone'] + geometry + ['cell']}
    y = test[outcome].to_numpy(float)
    losses, models, fits = {}, {}, {}
    for label, features in specs.items():
        model = AdditiveLogistic(features).fit(train, outcome)
        pred = model.predict(test)
        losses[label] = (pred - y) ** 2
        models[label] = {'brier': float(losses[label].mean()),
                         'logLoss': float(-(y * np.log(pred) + (1-y) * np.log1p(-pred)).mean()),
                         'meanPrediction': float(pred.mean()), 'iterations': model.iterations,
                         'maxParameterChange': model.max_delta}
        fits[label] = model
    result = {'minimumHistoricalHucks': min_hucks, 'eligiblePastPlayers': len(eligible), 'testPlayers': test.player.nunique(),
              'testGames': test.game.nunique(), 'testEvents': len(test), 'testSuccesses': int(y.sum()),
              'observedRate': float(y.mean()), 'models': models, 'comparisons': {}}
    for a, b in [('sharedGeometry', 'leagueGeometry'), ('sharedZone', 'player'), ('personalZone', 'sharedZone'),
                 ('sharedGeometry', 'sharedZone'), ('personalGeometry', 'sharedGeometry')]:
        dif = losses[a] - losses[b]
        result['comparisons'][a + 'Minus' + b[0].upper() + b[1:]] = {
            'gameBootstrap': cluster_ci(dif, test.game.to_numpy()),
            'playerBootstrap': cluster_ci(dif, test.player.to_numpy()),
            'relativeErrorChangePct': float(100 * dif.mean() / losses[b].mean())}
    if detail:
        # Examples selected for coverage, not how favorable their test result is.
        rows = []
        all_pred = {k: model.predict(test) for k, model in fits.items()}
        test['personalPrediction'] = all_pred['personalGeometry']
        test['sharedPrediction'] = all_pred['sharedGeometry']
        for (player, zone), z in test.groupby(['player', 'zone']):
            rows.append({'player': player, 'zone': zone, 'events': len(z), 'successes': int(z[outcome].sum()),
                         'sharedPrediction': float(z.sharedPrediction.mean()),
                         'personalPrediction': float(z.personalPrediction.mean())})
        result['testCells'] = rows
    return result


def study(d, names, test_year, first_year=2021, detailed=False):
    early = d[(d.season >= first_year) & (d.season < test_year)]
    later = d[d.season == test_year]
    assert not set(early.game) & set(later.game)
    eh, lh = early[early.huck], later[later.huck]
    # Restricted field depth avoids mistaking end-zone geometry for a personal habit.
    ec, lc = early[early.ty.between(20, 60, inclusive='left')], later[later.ty.between(20, 60, inclusive='left')]
    r = {'trainingSeasons': sorted(early.season.unique().tolist()), 'testSeason': test_year,
         'trainHucks': count(len(eh), eh.complete.sum()), 'testHucks': count(len(lh), lh.complete.sum()),
         'bestCompletionZone': best_zone(eh, lh, names),
         'completionPrediction': prediction_test(eh, lh, detail=detailed),
         'bestAttemptZone': best_zone(ec, lc, names, outcome='huck', zone_min=100),
         'attemptPredictionY20_60': prediction_test(ec, lc, 'huck', detail=detailed)}
    if detailed:
        r['largerSampleBestCompletionZone'] = best_zone(eh, lh, names, zone_min=20, min_hucks=100)
        r['zoneRates'] = [{'season': int(year), 'zone': zone, **count(len(z), z.complete.sum())}
                          for (year, zone), z in d[d.huck].groupby(['season', 'zone'])]
    else:
        for key in ['bestCompletionZone', 'bestAttemptZone']:
            del r[key]['rows']
    return r


def run():
    d, names, quality, hashes = load_data()
    print('Quality and source verification complete.', flush=True)
    studies = []
    for year in range(2022, 2027):
        print(f'Training on earlier seasons; evaluating {year}.', flush=True)
        studies.append(study(d, names, year, detailed=year == 2026))
    print('Checking sensitivity to using only 2024–2025 history.', flush=True)
    recent = study(d, names, 2026, first_year=2024)
    print('Checking prediction coverage with a 10-prior-huck floor.', flush=True)
    early, later = d[d.season < 2026], d[d.season == 2026]
    lower_floor = {
        'completionPrediction': prediction_test(early[early.huck], later[later.huck], detail=False, min_hucks=10),
        'attemptPredictionY20_60': prediction_test(
            early[early.ty.between(20, 60, inclusive='left')],
            later[later.ty.between(20, 60, inclusive='left')], 'huck', detail=False, min_hucks=10),
    }
    result = {
        'question': 'Do personal release-zone huck tendencies persist into later seasons, beyond league geometry?',
        'source': {'snapshot': '2026-10-12', 'tables': ['prod.throws', 'prod.games', 'prod.players'],
                   'sha256': hashes, 'liveRowCountReconciliation': '2026-10-24',
                   'freshnessCaveat': 'Computation uses exported rows. Live season counts match; row contents were not refetched or proven identical.'},
        'method': {
            'primary': 'Train on 2021–2025 regular seasons, evaluate 2026 regular season.',
            'chronologicalChecks': 'Expanding earlier history predicts 2022, 2023, 2024 and 2025 separately; folds overlap in training and players and are not independent experiments.',
            'huck': 'Nonstall pass; receiver Y minus thrower Y strictly >30 AND Euclidean distance strictly >40 yards.',
            'complete': 'Source turnover flag is false. Drops count as incomplete attempts.',
            'identity': 'Source PlayerID/Thrower, with one name per ID; same-name distinct IDs are not merged.',
            'bestZone': 'At least 40 prior hucks and at least two zones with 10 prior hucks. Choose highest raw completion, ties by attempts then zone ID. Compare against all other zones for same player. Raw selection is deliberately optimistic and is evaluated on a later season.',
            'attemptChoice': 'Release Y 20 to <60 only. At least 40 past hucks in this depth window; at least two zones with 100 throws and 5 hucks for a preferred-zone selection. Outcome is hucks / all located nonstall passes.',
            'prediction': 'Six regularized binomial models: league zone + geometry; player; player + shared zone; add player-zone interaction; player + shared zone + geometry; add interaction to geometry model. All fit on past years, with fixed penalties and no tuning on test outcomes. Main test cohort requires 40 past hucks; a sensitivity uses 10.',
            'geometryCompletion': '10-yard flight-length and forward-gain categories, plus whether the endpoint is in the scoring end zone. Conditional on attempted throw; these endpoint features are not known before a throw and do not represent an actionable pre-throw forecast.',
            'geometryAttempt': '10-yard release-depth categories, within Y20–60. Player + shared zone baseline already includes common left/center/right field tendencies.',
            'penalties': {'player': 2.5, 'sharedFeature': 1.0, 'playerZoneInteraction': 5.0},
            'uncertainty': '5,000 bootstrap resamples, seed 20261024. Loss differences resample entire test games and separately entire test players. Neither alone handles all crossed player/game/opponent dependence. Best-zone gaps resample players with equal player weight. Conditional on fitted historical models; no correction for multiple exploratory comparisons.',
            'limitations': ['Historical observational associations, not causal effects of changing release location.',
                            '2026 previously inspected; exploratory temporal validation, not preregistered or external untouched testing.',
                            'No receiver movement at release, defensive pressure, marking, wind, stall count or throw technique.',
                            'Season and team context, roles and opponents can change. Stable source IDs may still split an individual if upstream IDs change.',
                            'No claim of truly best coaching strategy follows from completion alone; possession value and alternatives matter.'],
        },
        'quality': quality, 'names': names, 'zones': ZONES,
        'studies': studies, 'recentHistorySensitivity': recent, 'lowerFloorSensitivity': lower_floor,
    }
    (HERE / 'multiseason_release_validation.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for s in studies + [recent]:
        print(json.dumps({'trainingSeasons': s['trainingSeasons'], 'testSeason': s['testSeason'],
                          'bestZone': {k: v for k, v in s['bestCompletionZone'].items() if k != 'rows'},
                          'completion': {k: v for k, v in s['completionPrediction'].items() if k != 'testCells'},
                          'attemptChoice': {k: v for k, v in s['attemptPredictionY20_60'].items() if k != 'testCells'}}, indent=2), flush=True)
    return result


if __name__ == '__main__':
    run()
