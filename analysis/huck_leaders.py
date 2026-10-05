"""Compare 2026 huck throwers using the website's preserved source snapshot.

Run with Python 3 from any directory. Writes the reviewed result beside this file;
does not update the website or its underlying data.
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'src/data.json'
data = json.loads(SNAPSHOT.read_text())
players = {p['id']: p['name'] for p in data['queries']['players']['rows']}
teams = {p['id']: p['name'] for p in data['queries']['teams']['rows']}


def is_huck(event):
    """Reconciles to all 1,152 available source player-game huck counts."""
    dx, dy = event['rx'] - event['tx'], event['ry'] - event['ty']
    return math.hypot(dx, dy) >= 40 and dy >= 30


def summarize(phase):
    events = [e for e in data['queries']['events']['rows']
              if phase == 'all' or e['phase'] == phase]
    assert len(events) == len({e['id'] for e in events})
    throws = collections.Counter(e['thrower'] for e in events)
    by_player = collections.defaultdict(list)
    for event in events:
        if is_huck(event):
            by_player[event['thrower']].append(event)
    rows = []
    for pid, hucks in by_player.items():
        attempts = len(hucks)
        completed = sum(e['complete'] for e in hucks)
        drops = sum(e['drop'] for e in hucks)
        scored = [e['throwAec'] for e in hucks if e['throwAec'] is not None]
        total = math.fsum(scored) if scored else None
        rows.append({
            'id': pid, 'player': players[pid],
            'team': ', '.join(sorted({teams[e['team']] for e in hucks})),
            'attempts': attempts, 'completions': completed, 'drops': drops,
            'completionPct': 100 * completed / attempts,
            'completionPctExcludingDrops': 100 * completed / (attempts - drops)
                if attempts > drops else None,
            'throwerAec': total, 'aecPerAttempt': total / attempts if total is not None else None,
            'huckPctOfThrows': 100 * attempts / throws[pid],
            'meanDistanceYards': math.fsum(math.hypot(e['rx'] - e['tx'], e['ry'] - e['ty']) for e in hucks) / attempts,
            'missingAec': attempts - len(scored),
        })
    rows.sort(key=lambda r: (-(r['aecPerAttempt'] if r['aecPerAttempt'] is not None else -math.inf), r['id']))
    hucks = [e for player_hucks in by_player.values() for e in player_hucks]
    return {
        'phase': phase, 'throws': len(events), 'hucks': len(hucks),
        'leagueCompletionPct': 100 * sum(e['complete'] for e in hucks) / len(hucks),
        'leagueAecPerAttempt': math.fsum(e['throwAec'] for e in hucks if e['throwAec'] is not None) / len(hucks),
        'missingHuckAec': sum(e['throwAec'] is None for e in hucks),
        'rows': rows,
        'qualifyingCounts': {str(n): sum(r['attempts'] >= n for r in rows) for n in [20, 25, 30, 40]},
    }


checked_games, checked_counts = set(), 0
for file in sorted((ROOT / 'data/source-api').glob('*.json')):
    payload = json.loads(file.read_text())
    if not isinstance(payload, dict) or not payload.get('game') or not payload.get('throws'):
        continue
    gid = payload['game']['GameID']
    if gid in checked_games:
        continue
    checked_games.add(gid)
    counts = collections.Counter()
    for throw in payload['throws']:
        projected = {'tx': float(throw['ThrowerX']), 'ty': float(throw['ThrowerY']),
                     'rx': float(throw['ReceiverX']), 'ry': float(throw['ReceiverY'])}
        if is_huck(projected):
            counts[throw['Thrower']] += 1
    for player in payload['playerStats']:
        assert counts[player['PlayerID']] == player['hucks_thrown'], (gid, player['PlayerID'])
        checked_counts += 1

result = {
    'snapshotGeneratedAt': data['generatedAt'],
    'snapshotSha256': hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
    'definition': 'A huck travels at least 40 yards from release to destination and gains at least 30 yards downfield.',
    'ranking': 'Observed thrower aEC per huck attempt; main comparison requires at least 30 attempts in the regular season.',
    'aecDefinition': 'Sum supplied thrower aEC, including negative throwaway credit and zero thrower credit for drops.',
    'completionDefinition': 'Completed hucks divided by all huck attempts, retaining drops as unsuccessful attempts.',
    'validation': {'sourceGames': len(checked_games), 'playerGameHuckCountsMatched': checked_counts, 'huckCountMismatches': 0},
    'caveats': [
        'The project has throw data for 131 of 132 regular-season games; July 18 Pittsburgh at Chicago is missing.',
        'These are observed 2026 results, not an isolated estimate of throwing talent or a guarantee on future throws.',
        'The cached league leaderboard includes playoffs and is not the same population as the main regular-season comparison.',
        'Shown Space completion percentages exclude dropped hucks from the denominator; the main comparison here includes them.',
    ],
    'regularSeason': summarize('Regular season'),
    'includingPlayoffs': summarize('all'),
}
for scope in ['regularSeason', 'includingPlayoffs']:
    qualified = [r for r in result[scope]['rows'] if r['attempts'] >= 30]
    assert all(r['missingAec'] == 0 for r in qualified)
output = Path(__file__).with_suffix('.json')
output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
print(json.dumps({
    'validation': result['validation'],
    'regularSeasonBaseline': {k: v for k, v in result['regularSeason'].items() if k != 'rows'},
    'regularSeasonTopEfficiency': [r for r in result['regularSeason']['rows'] if r['attempts'] >= 30][:6],
    'regularSeasonTopTotal': sorted(result['regularSeason']['rows'], key=lambda r: -(r['throwerAec'] or 0))[:3],
    'includingPlayoffsTopEfficiency': [r for r in result['includingPlayoffs']['rows'] if r['attempts'] >= 30][:3],
}, indent=2))
