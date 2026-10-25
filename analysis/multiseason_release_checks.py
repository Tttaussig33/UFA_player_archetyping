"""Independent row-by-row checks, without the primary pandas/zone helpers."""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent.parent
    exports = root / 'data/database-exports/2026-10-12'
    with (exports / 'games.csv').open() as handle:
        games = {r['GameID']: r for r in csv.DictReader(handle)}
    totals = Counter()
    by_player = defaultdict(Counter)
    with (exports / 'throws.csv').open() as handle:
        for r in csv.DictReader(handle):
            game = games[r['GameID']]
            if not game['RegularSeasonWeek'] or game['PlayoffRound']:
                continue
            if r['stall'] in ('1', '1.0', 'true', 'True'):
                continue
            if r['Thrower'].lower() in ('', 'unknown', 'null', 'none', 'nan'):
                continue
            try:
                x, y, rx, ry = [float(r[k]) for k in ('ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY')]
            except ValueError:
                continue
            if not all(map(math.isfinite, [x, y, rx, ry])):
                continue
            if not (-26.67000001 <= x <= 26.67000001 and -26.67000001 <= rx <= 26.67000001 and 0 <= y <= 120 and 0 <= ry <= 120):
                continue
            if not (ry - y > 30 and math.sqrt((rx - x) ** 2 + (ry - y) ** 2) > 40):
                continue
            year = int(game['Year'])
            complete = r['turnover'] not in ('1', '1.0', 'true', 'True')
            if y < 20:
                zone = 'own-endzone'
            elif x < -15:
                zone = 'left-build' if y < 60 else 'left-attack'
            elif x >= 15:
                zone = 'right-build' if y < 60 else 'right-attack'
            else:
                zone = 'center-init' if y < 40 else 'center-build' if y < 60 else 'center-attack' if y < 80 else 'center-red'
            totals[(year, 'hucks')] += 1
            totals[(year, 'completions')] += complete
            period = 'train' if year < 2026 else 'test'
            by_player[(r['Thrower'], period)][(zone, 'n')] += 1
            by_player[(r['Thrower'], period)][(zone, 'y')] += complete
    selected = []
    for (player, period), values in list(by_player.items()):
        if period != 'train':
            continue
        ns = {z: n for (z, k), n in values.items() if k == 'n'}
        zones = [z for z, n in ns.items() if n >= 10]
        if sum(ns.values()) < 40 or len(zones) < 2:
            continue
        z = sorted(zones, key=lambda z: (-values[(z, 'y')] / ns[z], -ns[z], z))[0]
        test = by_player.get((player, 'test'), Counter())
        test_n = sum(n for (zz, k), n in test.items() if k == 'n')
        if test[(z, 'n')] == 0 or test_n - test[(z, 'n')] == 0:
            continue
        selected.append((player, z, test[(z, 'n')], test[(z, 'y')], test_n - test[(z, 'n')],
                         sum(n for (zz, k), n in test.items() if k == 'y') - test[(z, 'y')]))
    result = json.loads((root / 'analysis/multiseason_release_validation.json').read_text())
    primary = result['studies'][-1]['bestCompletionZone']
    assert len(selected) == primary['testablePlayers']
    for row in result['quality']['seasonRows']:
        assert totals[(row['season'], 'hucks')] == row['hucks']
        assert totals[(row['season'], 'completions')] == row['completedHucks']
    observed = [sum(row[i] for row in selected) for i in range(2, 6)]
    expected = [primary['test']['chosen']['attempts'], primary['test']['chosen']['successes'],
                primary['test']['other']['attempts'], primary['test']['other']['successes']]
    assert observed == expected
    expected_players = {r['player']: r['zone'] for r in primary['rows'] if r['test']['gap'] is not None}
    assert {r[0]: r[1] for r in selected} == expected_players
    return {'independentlyMatchedHucks': sum(totals[(y, 'hucks')] for y in range(2021, 2027)),
            'independentlyMatchedCompletions': sum(totals[(y, 'completions')] for y in range(2021, 2027)),
            'independentlyMatchedTestPlayers': len(selected),
            'testChosenAttempts': observed[0], 'testChosenCompletions': observed[1],
            'testOtherAttempts': observed[2], 'testOtherCompletions': observed[3]}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
