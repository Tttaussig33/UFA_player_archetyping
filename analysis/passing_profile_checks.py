"""Independent CSV-reader reconciliation of 2026 profile totals and matching.

Does not import the study's aggregation, filtering, scaling, or ranking functions.
Run after passing_profile_validation.py. No database or network access.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / 'data/database-exports/2026-10-12'


def check():
    result = json.loads((ROOT / 'analysis/passing_profile_validation.json').read_text())
    primary = result['studies'][-1]
    with (EXPORTS / 'games.csv').open() as f:
        games = {r['GameID']: r for r in csv.DictReader(f)}
    stats = defaultdict(lambda: dict(throws=0, catches=0, completions=0,
        short=0, huck=0, forward=0, backward=0, releaseTotal=0.0,
        catchTotal=0.0, releaseSide=0, catchSide=0, throwGames=set(), catchGames=set()))
    regular_games = {}
    sums = dict(events=0, throws=0, catches=0)
    cutoff = primary['cutoff']
    missing_ids = {'', 'unknown', 'none', 'null', 'nan'}
    with (EXPORTS / 'throws.csv').open() as f:
        for r in csv.DictReader(f):
            g = games[r['GameID']]
            if g['Year'] != '2026' or not g['RegularSeasonWeek'] or g['PlayoffRound'] or r['stall'] == '1.0':
                continue
            try:
                tx, ty, rx, ry = (float(r[c]) for c in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY'])
            except ValueError:
                continue
            if not (all(math.isfinite(v) for v in [tx, ty, rx, ry]) and
                    -26.67000001 <= tx <= 26.67000001 and -26.67000001 <= rx <= 26.67000001 and
                    0 <= ty <= 120 and 0 <= ry <= 120):
                continue
            sums['events'] += 1
            day = g['StartTimestamp'][:10]
            regular_games[r['GameID']] = day
            half = 'early' if day < cutoff else 'late'
            team = g['HomeTeamID'] if r['is_home_team'] == 'true' else g['AwayTeamID']
            complete = r['turnover'] == '0.0'
            if r['Thrower'].lower() not in missing_ids:
                sums['throws'] += 1
                s = stats[(team, r['Thrower'], half)]
                s['throws'] += 1
                s['completions'] += complete
                s['throwGames'].add(r['GameID'])
                s['short'] += math.dist((tx, ty), (rx, ry)) <= 10
                s['huck'] += ry - ty > 30 and math.dist((tx, ty), (rx, ry)) > 40
                s['forward'] += ry - ty > abs(rx - tx)
                s['backward'] += ty - ry > abs(rx - tx)
                s['releaseTotal'] += ty
                s['releaseSide'] += abs(tx) >= 15
            if complete and r['Receiver'].lower() not in missing_ids:
                sums['catches'] += 1
                s = stats[(team, r['Receiver'], half)]
                s['catches'] += 1
                s['catchGames'].add(r['GameID'])
                s['catchTotal'] += ry
                s['catchSide'] += abs(rx) >= 15
    assert sums == dict(events=72601, throws=72590, catches=67820)
    assert sorted(regular_games.values())[len(regular_games) // 2] == cutoff
    assert len([d for d in regular_games.values() if d < cutoff]) == primary['earlyGames']
    assert len([d for d in regular_games.values() if d >= cutoff]) == primary['laterGames']
    player_teams = defaultdict(set)
    for team, player, half in stats: player_teams[player].add(team)
    profiles = {}
    for (team, player, half), s in stats.items():
        if len(player_teams[player]) != 1 or min(s['throws'], s['catches']) < 100:
            continue
        if min(len(s['throwGames']), len(s['catchGames'])) < 3: continue
        profiles[(player, half)] = dict(team=team, throws=s['throws'], catches=s['catches'],
            completions=s['completions'], throwGames=len(s['throwGames']), catchGames=len(s['catchGames']),
            shortShare=s['short']/s['throws'], huckShare=s['huck']/s['throws'],
            forwardShare=s['forward']/s['throws'], backwardShare=s['backward']/s['throws'],
            releaseY=s['releaseTotal']/s['throws'], releaseSide=s['releaseSide']/s['throws'],
            catchY=s['catchTotal']/s['catches'], catchSide=s['catchSide']/s['catches'],
            throwShare=s['throws']/(s['throws'] + s['catches']))
    early = {pid: row for (pid, half), row in profiles.items() if half == 'early'}
    later = {pid: row for (pid, half), row in profiles.items() if half == 'late' and pid in early}
    assert len(early) == primary['referencePlayers'] and len(later) == primary['evaluatedPlayers']
    features = list(result['design']['features'])
    means = {f: mean(r[f] for r in early.values()) for f in features}
    scales = {f: pstdev(r[f] for r in early.values()) for f in features}
    for f in features:
        assert math.isclose(means[f], primary['scalerMean'][f], abs_tol=1e-10)
        assert math.isclose(scales[f], primary['scalerSD'][f], abs_tol=1e-10)
    weights = primary['featureWeights']
    assert math.isclose(sum(weights.values()), 1.0)
    for group in {v['group'] for v in result['design']['features'].values()}:
        assert math.isclose(sum(weights[f] for f in features if result['design']['features'][f]['group'] == group), .25)
    metrics = defaultdict(list)
    all_records = {r['player']: r for r in primary['players']}
    assert all_records.keys() == later.keys()
    for pid, row in later.items():
        record = all_records[pid]
        for period, data in [('early', early[pid]), ('later', row)]:
            for k, value in data.items():
                if isinstance(value, str): assert value == record[period][k]
                else: assert math.isclose(value, record[period][k], abs_tol=1e-10), (pid, period, k)
        distances = {candidate: math.sqrt(sum(weights[f] * ((row[f] - e[f])/scales[f])**2 for f in features))
                     for candidate, e in early.items()}
        own = distances[pid]
        assert math.isclose(own, record['ownDistance'], abs_tol=1e-10)
        ahead = sum(d < own - 1e-12 for d in distances.values())
        ties = sum(abs(d - own) <= 1e-12 for d in distances.values())
        assert record['ownRank'] == 1 + ahead + (ties - 1)/2
        metrics['top1'].append(1/ties if ahead == 0 else 0)
        metrics['top5'].append(max(0, min(1, (5-ahead)/ties)))
        metrics['fractionOfOtherPlayersBeaten'].append(1 - (ahead+(ties-1)/2)/(len(early)-1))
        teammates = [c for c in early if early[c]['team'] == early[pid]['team']]
        if len(teammates) >= 4:
            ahead = sum(distances[c] < own-1e-12 for c in teammates)
            ties = sum(abs(distances[c]-own) <= 1e-12 for c in teammates)
            metrics['withinTeamTop1'].append(1/ties if ahead == 0 else 0)
            metrics['withinTeamFractionBeaten'].append(1 - (ahead+(ties-1)/2)/(len(teammates)-1))
    for metric, values in metrics.items():
        assert math.isclose(mean(values), primary[metric]['mean'], abs_tol=1e-10), metric
    # Reconcile the follow-up without borrowing its rank or distance functions.
    peer_values = []
    for r in result['neighborFollowup']['primary100']['rows']:
        pid = r['player']
        candidates = [c for c in later if early[c]['team'] != early[pid]['team']]
        def distance(a, b): return math.sqrt(sum(weights[f] * ((a[f]-b[f])/scales[f])**2 for f in features))
        selected = sorted(candidates, key=lambda c: (distance(early[pid], early[c]), c))[:5]
        assert selected == r['earlierChosenNeighbors']
        late_d = {c: distance(later[pid], later[c]) for c in candidates}
        percentiles = []
        for c in selected:
            ahead = sum(v < late_d[c] for v in late_d.values())
            ties = sum(v == late_d[c] for v in late_d.values())
            percentiles.append(1 - (ahead+(ties-1)/2)/(len(candidates)-1))
        assert math.isclose(mean(percentiles), r['laterSimilarityPercentile'], abs_tol=1e-10)
        peer_values.append(mean(percentiles))
    assert math.isclose(mean(peer_values), result['neighborFollowup']['primary100']['meanLaterSimilarityPercentile'], abs_tol=1e-10)
    return dict(independent2026Events=sums['events'], namedThrows=sums['throws'],
        completedNamedCatches=sums['catches'], matchedReferenceProfiles=len(early),
        matchedLaterProfiles=len(later), checkedFieldsPerProfile=9,
        checkedPrimaryMatchingMetrics=len(metrics), checkedPeerRows=len(peer_values))


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
