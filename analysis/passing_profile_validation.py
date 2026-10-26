"""Test whether recorded offensive passing styles persist across later games.

Fixed design written before inspecting this experiment's results. Exploratory:
the source seasons have been used in earlier huck analyses. No clustering, skill
ranking, or claims of interchangeable players are inferred from re-identification.
Read-only October 12 exports; writes aggregate/profile results, never raw events.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from multiseason_release_validation import EXPORTS, digest

HERE = Path(__file__).resolve().parent
SEED = 20261026
BOOTSTRAPS = 5000
FEATURES = {
    'shortShare': ('Passing choices', 'Short throws (≤10 yd)', '%'),
    'huckShare': ('Passing choices', 'Hucks (>30 yd gain and >40 yd flight)', '%'),
    'forwardShare': ('Passing choices', 'Forward throws (<45° from downfield)', '%'),
    'backwardShare': ('Passing choices', 'Backward throws (<45° from upfield)', '%'),
    'releaseY': ('Release locations', 'Average release position', 'yd'),
    'releaseSide': ('Release locations', 'Releases near either sideline (|X|≥15)', '%'),
    'catchY': ('Catch locations', 'Average completed-catch position', 'yd'),
    'catchSide': ('Catch locations', 'Completed catches near either sideline (|X|≥15)', '%'),
    'throwShare': ('Disc involvement', 'Throws / (throws + completed catches)', '%'),
}
GROUPS = list(dict.fromkeys(v[0] for v in FEATURES.values()))
EXAMPLE_IDS = ['aatkins', 'sfaris', 'ograff', 'gsanner', 'awilsonho']


def load_events():
    manifest = json.loads((EXPORTS / 'manifest.json').read_text())
    hashes = {}
    for table in ['throws', 'games', 'players', 'teams']:
        hashes[table] = digest(EXPORTS / f'{table}.csv')
        assert hashes[table] == manifest['tables'][table]['sha256'], table
    games = pd.read_csv(EXPORTS / 'games.csv', dtype=str, keep_default_na=False)
    players = pd.read_csv(EXPORTS / 'players.csv', dtype=str, keep_default_na=False)
    teams = pd.read_csv(EXPORTS / 'teams.csv', dtype=str, keep_default_na=False)
    cols = ['GameID', 'throw_sig_id', 'Thrower', 'Receiver', 'ThrowerX', 'ThrowerY',
            'ReceiverX', 'ReceiverY', 'turnover', 'stall', 'is_home_team']
    events = pd.read_csv(EXPORTS / 'throws.csv', usecols=cols, dtype=str, keep_default_na=False)
    assert not games.GameID.duplicated().any()
    assert not events[['GameID', 'throw_sig_id']].duplicated().any()
    assert events.throw_sig_id.ne('').all()
    assert events.is_home_team.isin(['true', 'false']).all()
    assert events.turnover.isin(['0.0', '1.0']).all()
    assert events.stall.isin(['0.0', '1.0']).all()
    assert players.groupby('PlayerID').full_name.nunique().max() == 1
    names = players.drop_duplicates('PlayerID').set_index('PlayerID').full_name.to_dict()
    team_names = teams.drop_duplicates(['Year', 'TeamID']).set_index(['Year', 'TeamID']).FullName.to_dict()
    events = events.merge(games[['GameID', 'Year', 'StartTimestamp', 'RegularSeasonWeek',
                                'PlayoffRound', 'HomeTeamID', 'AwayTeamID']],
                          on='GameID', validate='many_to_one', how='left', indicator=True)
    assert events._merge.eq('both').all()
    events['season'] = pd.to_numeric(events.Year).astype(int)
    for original, new in [('ThrowerX', 'tx'), ('ThrowerY', 'ty'), ('ReceiverX', 'rx'), ('ReceiverY', 'ry')]:
        events[new] = pd.to_numeric(events[original], errors='coerce')
    events['game'] = events.GameID
    events['day'] = pd.to_datetime(events.StartTimestamp, errors='coerce').dt.strftime('%Y-%m-%d')
    events['team'] = np.where(events.is_home_team.eq('true'), events.HomeTeamID, events.AwayTeamID)
    events['distance'] = np.hypot(events.rx - events.tx, events.ry - events.ty)
    events['gain'] = events.ry - events.ty
    events['complete'] = events.turnover.eq('0.0')
    events['short'] = events.distance.le(10)
    events['huck'] = events.gain.gt(30) & events.distance.gt(40)
    events['forward'] = events.gain.gt((events.rx - events.tx).abs())
    events['backward'] = (-events.gain).gt((events.rx - events.tx).abs())
    events['releaseSide'] = events.tx.abs().ge(15)
    events['catchSide'] = events.rx.abs().ge(15)
    missing_ids = ['', 'unknown', 'none', 'null', 'nan']
    events['namedThrower'] = ~events.Thrower.str.lower().isin(missing_ids)
    events['namedReceiver'] = ~events.Receiver.str.lower().isin(missing_ids)
    finite = np.isfinite(events[['tx', 'ty', 'rx', 'ry']]).all(axis=1)
    bounds = (events.tx.between(-26.67000001, 26.67000001) & events.ty.between(0, 120) &
              events.rx.between(-26.67000001, 26.67000001) & events.ry.between(0, 120))
    regular = events.RegularSeasonWeek.ne('') & events.PlayoffRound.eq('') & events.season.between(2021, 2026)
    eligible = regular & events.stall.eq('0.0') & finite & bounds
    kept = events[eligible].copy()
    assert kept.day.notna().all()
    assert kept.loc[kept.namedThrower, 'Thrower'].isin(names).all()
    assert kept.loc[kept.namedReceiver, 'Receiver'].isin(names).all()
    quality = {
        'sourceRows': len(events), 'eligibleLocatedNonstallEvents': len(kept),
        'namedThrows': int(kept.namedThrower.sum()),
        'completedNamedCatches': int((kept.complete & kept.namedReceiver).sum()),
        'completedCatchesFromUnnamedThrowers': int((kept.complete & kept.namedReceiver & ~kept.namedThrower).sum()),
        'excludedStallsRegular': int((regular & events.stall.eq('1.0')).sum()),
        'excludedInvalidGeometryRegularNonstall': int((regular & events.stall.eq('0.0') & ~(finite & bounds)).sum()),
        'completeButUnnamedReceiver': int((kept.complete & ~kept.namedReceiver).sum()),
        'dateDisagreements': kept.loc[kept.day.ne(kept.GameID.str[:10]),
            ['GameID', 'StartTimestamp']].drop_duplicates().to_dict('records'),
        'duplicateGameThrowKeys': 0, 'orphanGames': 0,
    }
    assert quality['namedThrows'] == 456555  # Reconcile the prior audited scope.
    # A game is never split; actual StartTimestamp handles the rescheduled 2025 game.
    cutoffs = {}
    for year, rows in kept.groupby('season'):
        days = rows[['game', 'day']].drop_duplicates().day.sort_values()
        cutoffs[int(year)] = days.iloc[len(days) // 2]
    kept['half'] = np.where(kept.day < kept.season.map(cutoffs), 'early', 'late')
    quality['seasonCounts'] = [dict(season=int(year), events=len(rows),
        namedThrows=int(rows.namedThrower.sum()), games=int(rows.game.nunique()),
        catches=int((rows.complete & rows.namedReceiver).sum()), cutoff=cutoffs[int(year)])
        for year, rows in kept.groupby('season')]
    return kept, names, team_names, hashes, quality, cutoffs


def aggregate(events, half=True):
    """One row per player/team/season/period, independently aggregate both roles."""
    keys = ['season', 'team', 'player'] + (['half'] if half else [])
    outgoing = events[events.namedThrower].rename(columns={'Thrower': 'player'})
    incoming = events[events.namedReceiver & events.complete].rename(columns={'Receiver': 'player'})
    throws = outgoing.groupby(keys).agg(throws=('game', 'size'), throwGames=('game', 'nunique'),
        shortShare=('short', 'mean'), huckShare=('huck', 'mean'),
        forwardShare=('forward', 'mean'), backwardShare=('backward', 'mean'),
        releaseY=('ty', 'mean'), releaseSide=('releaseSide', 'mean'),
        completions=('complete', 'sum'))
    catches = incoming.groupby(keys).agg(catches=('game', 'size'), catchGames=('game', 'nunique'),
        catchY=('ry', 'mean'), catchSide=('catchSide', 'mean'))
    profiles = throws.join(catches, how='outer').reset_index()
    for name in ['throws', 'throwGames', 'catches', 'catchGames', 'completions']:
        profiles[name] = profiles[name].fillna(0).astype(int)
    profiles['throwShare'] = profiles.throws / (profiles.throws + profiles.catches)
    # Multi-team seasons need a separate transfer/role-change design.
    team_counts = profiles.groupby(['season', 'player']).team.transform('nunique')
    profiles['singleTeam'] = team_counts.eq(1)
    return profiles


def qualify(profiles, minimum=100, games=3):
    return profiles[profiles.singleTeam & profiles.throws.ge(minimum) & profiles.catches.ge(minimum) &
                    profiles.throwGames.ge(games) & profiles.catchGames.ge(games)].copy()


def interval(values, teams):
    """Resample reference-team clusters, conditional on fitted reference profiles."""
    grouped = pd.DataFrame({'v': values, 'team': teams}).groupby('team').v.agg(['sum', 'size'])
    if len(grouped) < 10:
        return dict(mean=float(np.mean(values)) if len(values) else None, ci95=None,
                    teams=len(grouped), players=len(values),
                    intervalOmitted='Fewer than 10 reference-team clusters; no reliable cluster interval.')
    rng = np.random.default_rng(SEED)
    ix = rng.integers(0, len(grouped), (BOOTSTRAPS, len(grouped)))
    b = grouped['sum'].to_numpy()[ix].sum(axis=1) / grouped['size'].to_numpy()[ix].sum(axis=1)
    return dict(mean=float(np.mean(values)), ci95=np.quantile(b, [.025, .975]).tolist(),
                teams=len(grouped), players=len(values))


def match(early, later, features=None):
    features = list(FEATURES) if features is None else features
    assert not early.player.duplicated().any() and not later.player.duplicated().any()
    early = early.sort_values('player').reset_index(drop=True)
    later = later[later.player.isin(early.player)].sort_values('player').reset_index(drop=True)
    assert len(early) > 5 and len(later) > 5
    # Every normalization parameter uses early data only, including early-only candidates.
    means = early[features].mean()
    scales = early[features].std(ddof=0)
    assert scales.gt(0).all()
    groups = [FEATURES[f][0] for f in features]
    weights = np.array([1 / (len(set(groups)) * groups.count(FEATURES[f][0])) for f in features])
    ref = ((early[features] - means) / scales).to_numpy(float)
    query = ((later[features] - means) / scales).to_numpy(float)
    distances = np.sqrt(((query[:, None, :] - ref[None, :, :]) ** 2 * weights).sum(axis=2))
    ref_ids = early.player.to_numpy()
    indices = pd.Series(np.arange(len(early)), index=early.player).loc[later.player].to_numpy()
    own = distances[np.arange(len(later)), indices]
    # Fractional credit for exact ties avoids benefiting a player-ID sort order.
    eps = 1e-12
    closer = (distances < own[:, None] - eps).sum(axis=1)
    tied = np.isclose(distances, own[:, None], rtol=0, atol=eps).sum(axis=1)
    top1 = np.where(closer == 0, 1 / tied, 0)
    top5 = np.clip((5 - closer) / tied, 0, 1)
    better = 1 - (closer + (tied - 1) / 2) / (len(early) - 1)
    early_teams = early.team.to_numpy()
    ref_team = early_teams[indices]
    team_mask = ref_team[:, None] == early_teams[None, :]
    n_team = team_mask.sum(axis=1)
    in_team_closer = ((distances < own[:, None] - eps) & team_mask).sum(axis=1)
    in_team_tied = (np.isclose(distances, own[:, None], rtol=0, atol=eps) & team_mask).sum(axis=1)
    team_top = np.where(in_team_closer == 0, 1 / in_team_tied, 0)
    team_better = 1 - (in_team_closer + (in_team_tied - 1) / 2) / np.maximum(n_team - 1, 1)
    team_eval = n_team >= 4
    result = {
        'referencePlayers': len(early), 'evaluatedPlayers': len(later),
        'earlyThrowsEvaluatedPlayers': int(early.set_index('player').loc[later.player].throws.sum()),
        'laterThrows': int(later.throws.sum()), 'laterCatches': int(later.catches.sum()),
        'top1': interval(top1, ref_team), 'top5': interval(top5, ref_team),
        'randomTop1': 1 / len(early), 'randomTop5': 5 / len(early),
        'fractionOfOtherPlayersBeaten': interval(better, ref_team),
        'withinTeamTop1': interval(team_top[team_eval], ref_team[team_eval]),
        'withinTeamRandomTop1': float((1 / n_team[team_eval]).mean()) if team_eval.any() else None,
        'withinTeamFractionBeaten': interval(team_better[team_eval], ref_team[team_eval]),
        'withinTeamCandidatesRange': [int(n_team[team_eval].min()), int(n_team[team_eval].max())] if team_eval.any() else None,
        'scalerMean': means.to_dict(), 'scalerSD': scales.to_dict(),
        'features': features, 'featureWeights': dict(zip(features, weights.tolist())),
    }
    aligned = early.set_index('player').loc[later.player].reset_index()
    result['featureStability'] = []
    for f in features:
        result['featureStability'].append(dict(feature=f, label=FEATURES[f][1],
            spearman=float(aligned[f].rank().corr(later[f].rank())),
            medianAbsoluteChange=float(np.median(np.abs(aligned[f].to_numpy() - later[f].to_numpy())))))
    records = []
    columns = list(FEATURES) + ['throws', 'catches', 'throwGames', 'catchGames', 'completions', 'team']
    for i, row in later.iterrows():
        other_indices = np.argsort(distances[i], kind='stable')
        other_indices = [j for j in other_indices if ref_ids[j] != row.player][:3]
        records.append(dict(player=row.player, ownRank=float(1 + closer[i] + (tied[i] - 1) / 2),
            ownDistance=float(own[i]), ownBeatsFraction=float(better[i]),
            withinTeamRank=float(1 + in_team_closer[i] + (in_team_tied[i] - 1) / 2),
            withinTeamCandidates=int(n_team[i]),
            early={c: aligned.iloc[i][c] for c in columns}, later={c: row[c] for c in columns},
            nearestOtherEarlierProfiles=[dict(player=ref_ids[j], distance=float(distances[i, j])) for j in other_indices]))
    result['players'] = records
    changed = aligned.team.ne(later.team).to_numpy()
    result['teamChanges'] = dict(players=int(changed.sum()),
        fractionOfOthersBeaten=float(better[changed].mean()) if changed.any() else None,
        top1=float(top1[changed].mean()) if changed.any() else None)
    return result


def serialize(value):
    if isinstance(value, np.integer): return int(value)
    if isinstance(value, np.floating): return float(value)
    if isinstance(value, np.bool_): return bool(value)
    raise TypeError(type(value).__name__)


def compact(result):
    return {k: v for k, v in result.items() if k not in ['players', 'scalerMean', 'scalerSD']}


def neighbor_followup(early, later):
    """Exploratory follow-up added after the first positive self-matching result.

    Do early cross-team neighbors remain relatively similar later? This is
    descriptive, with no interval treating overlapping player pairs as independent.
    All nine features/weights stay fixed; no outcome-based metric tuning.
    """
    features = list(FEATURES)
    means, scales = early[features].mean(), early[features].std(ddof=0)
    later = later[later.player.isin(early.player)].sort_values('player').reset_index(drop=True)
    aligned = early.set_index('player').loc[later.player].reset_index()
    weights = np.array([1 / (len(GROUPS) * sum(FEATURES[k][0] == FEATURES[f][0] for k in features)) for f in features])
    before = ((aligned[features] - means) / scales).to_numpy(float)
    after = ((later[features] - means) / scales).to_numpy(float)
    previous_distance = np.sqrt(((before[:, None, :] - before[None, :, :]) ** 2 * weights).sum(axis=2))
    later_distance = np.sqrt(((after[:, None, :] - after[None, :, :]) ** 2 * weights).sum(axis=2))
    rows = []
    for i, p in later.iterrows():
        candidates = np.flatnonzero(aligned.team.to_numpy() != aligned.iloc[i].team)
        if len(candidates) < 6: continue
        selected = candidates[np.argsort(previous_distance[i, candidates], kind='stable')[:5]]
        # On a later-only ranking, random neighbors average the 50th percentile.
        ranks = pd.Series(later_distance[i, candidates]).rank(method='average').to_numpy()
        positions = {j: k for k, j in enumerate(candidates)}
        percentiles = [1 - (ranks[positions[j]] - 1) / (len(candidates) - 1) for j in selected]
        rows.append(dict(player=p.player, laterSimilarityPercentile=float(np.mean(percentiles)),
            meanLaterDistanceSelected=float(later_distance[i, selected].mean()),
            meanLaterDistanceAll=float(later_distance[i, candidates].mean()),
            earlierChosenNeighbors=later.iloc[selected].player.tolist(), candidates=len(candidates)))
    return dict(evaluatedPlayers=len(rows), chosenNeighborsPerPlayer=5,
        meanLaterSimilarityPercentile=float(np.mean([r['laterSimilarityPercentile'] for r in rows])),
        randomExpectedPercentile=0.5, rows=rows,
        caveat='Exploratory follow-up after seeing the positive self-matching result. Cross-team pairs overlap; no independence-based confidence interval. Similarity is not quality or replacement success.')


def run():
    events, names, team_names, hashes, quality, cutoffs = load_events()
    halves = aggregate(events)
    annual = aggregate(events, half=False)
    studies = []
    primary_early = primary_late = None
    for season in [2023, 2024, 2025, 2026]:
        scope = halves[halves.season.eq(season)]
        eligible = qualify(scope)
        early, late = eligible[eligible.half.eq('early')], eligible[eligible.half.eq('late')]
        result = match(early, late)
        rows = events[events.season.eq(season)]
        result.update(season=season, cutoff=cutoffs[season],
            earlyGames=int(rows.loc[rows.half.eq('early'), 'game'].nunique()),
            laterGames=int(rows.loc[rows.half.eq('late'), 'game'].nunique()),
            earlyQualified=len(early), laterQualified=len(late),
            multiTeamPlayersExcluded=int(scope.loc[~scope.singleTeam, 'player'].nunique()))
        studies.append(result)
        if season == 2026: primary_early, primary_late = early, late
        print(f'{season}: {result["evaluatedPlayers"]} later players / {len(early)} early candidates; '
              f'own rank beats {result["fractionOfOtherPlayersBeaten"]["mean"]:.1%}; '
              f'top1 {result["top1"]["mean"]:.1%}; within team {result["withinTeamTop1"]["mean"]:.1%}')
    sensitivity = {}
    for minimum in [50, 150]:
        s = qualify(halves[halves.season.eq(2026)], minimum=minimum)
        sensitivity[f'minimum{minimum}'] = compact(match(s[s.half.eq('early')], s[s.half.eq('late')]))
    for group in GROUPS:
        sensitivity['only' + group] = compact(match(primary_early, primary_late,
            [f for f in FEATURES if FEATURES[f][0] == group]))
        sensitivity['without' + group] = compact(match(primary_early, primary_late,
            [f for f in FEATURES if FEATURES[f][0] != group]))
    neighbors = {'primary100': neighbor_followup(primary_early, primary_late)}
    broad = qualify(halves[halves.season.eq(2026)], minimum=50)
    neighbors['broader50'] = neighbor_followup(broad[broad.half.eq('early')], broad[broad.half.eq('late')])
    qualifying_years = qualify(annual, minimum=200, games=6)
    across_years = match(qualifying_years[qualifying_years.season.eq(2025)],
                         qualifying_years[qualifying_years.season.eq(2026)])
    across_years.update(referenceSeason=2025, laterSeason=2026)
    for result in [*studies, across_years]:
        for p in result['players']:
            p['name'] = names[p['player']]
            for n in p['nearestOtherEarlierProfiles']: n['name'] = names[n['player']]
    primary = studies[-1]
    examples = [p for p in primary['players'] if p['player'] in EXAMPLE_IDS]
    results = dict(study='Offensive passing-profile stability', analysisDate='2026-10-26',
        sourceSnapshot='2026-10-12', sourceHashes=hashes, quality=quality,
        design=dict(primary='2026 early vs later regular-season games; repeat 2023–2025.',
            split='Actual game StartTimestamp date; early is strictly before the season median recorded-game date.',
            eligibility='At least 100 throws AND 100 completed named catches, across at least 3 games in EACH role and period; single team within season.',
            features={k: dict(group=v[0], label=v[1], displayUnit=v[2],
                             storedUnit='fraction' if v[2] == '%' else 'yards') for k, v in FEATURES.items()},
            distance='Early-only z scores; mean squared difference within each of four feature groups, equal group weight; square root.',
            reference='Every early-qualified player, including those not qualifying later. Later evaluation requires the same source ID in the early reference.',
            uncertainty='5,000 reference-team cluster bootstrap samples of per-player match metrics; conditional on the fixed profiles, scales and candidate pool.',
            limitations=['Exploratory temporal validation; previously inspected seasons, not new external data.',
                'Disc involvement only; no on-field exposure, routes, marking, weather or off-disc defense.',
                'Re-identification does not validate discrete archetypes, player quality or replacement success.',
                'Repeated seasons and players are dependent; thresholds select regular high-involvement players.',
                'Completed catches omit unsuccessful target routes. Completion is kept out of similarity.',
                'Team bootstrap does not propagate profile estimation or all opponent/game dependence.',
                'Matching two players with each other is not proof their similarity persists in future games.']),
        studies=studies, sensitivities=sensitivity, acrossSeasons=across_years,
        neighborFollowup=neighbors, examples=examples)
    path = HERE / 'passing_profile_validation.json'
    path.write_text(json.dumps(results, default=serialize, indent=2, allow_nan=False) + '\n')
    print(f'Saved {path}')
    return results


if __name__ == '__main__':
    run()
