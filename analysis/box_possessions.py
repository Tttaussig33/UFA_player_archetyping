"""Compare hypothetical paths among the eleven offensive box leaders.

The screen is descriptive, in-sample, and deliberately separate from aEC.
Run from any directory with Python 3; reuses the snapshot validation loader.
"""
from __future__ import annotations
import collections
import json
import math
import statistics
from pathlib import Path
from ideal_possessions import load

OUT = Path(__file__).resolve().parent
NODES = {
    'init': ('aatkins', 'Atkins', 0, 30),
    'left-build': ('khenke', 'Henke', -20.825, 40),
    'right-build': ('sfaris', 'Faris', 20.825, 40),
    'build': ('glarson', 'Larson', 0, 50),
    'attack': ('tdecraene', 'Decraene', 0, 70),
    'left-attack': ('khenke', 'Henke', -20.825, 80),
    'right-attack': ('tdecraene', 'Decraene', 20.825, 80),
    'red': ('ograff', 'Graff', 0, 90),
    'goal-left': ('gsanner', 'Sanner', -13.325, 105),
    'goal-right': ('awilsonho', 'Wilson Holliday', 13.325, 105),
    'goal-deep': ('rpieran', 'Robert', 0, 115),
}


def zone(x, y, release=False):
    if x is None or y is None or abs(x) > 26.670001 or not 0 <= y <= 120:
        return None
    if y >= 100 and not (release and y == 100):
        return 'goal-deep' if y >= 110 else 'goal-left' if x < 0 else 'goal-right'
    if y < 20:
        return 'own'
    if x < -15:
        return 'left-build' if y < 60 else 'left-attack'
    if x >= 15:
        return 'right-build' if y < 60 else 'right-attack'
    return 'init' if y < 40 else 'build' if y < 60 else 'attack' if y < 80 else 'red'


def terminal(node):
    return node.startswith('goal-')


def delivered(e, dest):
    # A completed catch on the goal line is not necessarily an explicit goal.
    return e['drop'] or (e['complete'] and (not terminal(dest) or e['goal']))


def stats(rows, dest):
    return {
        'attempts': len(rows), 'completions': sum(e['complete'] for e in rows),
        'drops': sum(e['drop'] for e in rows),
        'deliveries': sum(delivered(e, dest) for e in rows),
        'goals': sum(e['complete'] and e['goal'] for e in rows),
        'games': len({e['game'] for e in rows}),
        'meanObservedAec': statistics.mean(e['aec'] for e in rows if e['aec'] is not None) if rows else None,
        'eventIds': [e['id'] for e in rows],
    }


def main():
    snapshot, rows = load()
    people = {p['id']: p['name'] for p in snapshot['queries']['players']['rows']}
    throws, catches, league = (collections.defaultdict(list) for _ in range(3))
    box_totals = collections.defaultdict(lambda: collections.defaultdict(float))
    for e in rows:
        a, b = zone(e['tx'], e['ty'], True), zone(e['rx'], e['ry'])
        if a in NODES and not terminal(a) and e['throwAec'] is not None:
            box_totals[a][e['thrower']] += e['throwAec']
        if b in NODES and terminal(b) and e['receiver'] and (e['complete'] or e['drop']) and e['receiveAec'] is not None:
            box_totals[b][e['receiver']] += e['receiveAec']
        if a not in NODES or b not in NODES:
            continue
        league[a, b].append(e)
        if e['thrower'] == NODES[a][0]:
            throws[a, b].append(e)
        if e['receiver'] == NODES[b][0] and delivered(e, b):
            catches[a, b].append(e)
    for node, (pid, *_rest) in NODES.items():
        assert max(box_totals[node], key=box_totals[node].get) == pid

    def edge(a, b, strength=40):
        t, c, base = throws[a, b], catches[a, b], league[a, b]
        delivery_n = sum(delivered(e, b) for e in base)
        success_n = sum(e['complete'] and (not terminal(b) or e['goal']) for e in base)
        delivery_prior = (delivery_n + .5) / (len(base) + 1)
        catch_prior = (success_n + .5) / (delivery_n + 1)
        pt = (sum(delivered(e, b) for e in t) + strength * delivery_prior) / (len(t) + strength)
        pr = (sum(e['complete'] for e in c) + strength * catch_prior) / (len(c) + strength)
        return {'from': a, 'to': b, 'thrower': NODES[a][0], 'receiver': NODES[b][0],
                'throw': stats(t, b), 'catch': stats(c, b),
                'league': stats(base, b), 'screenIndex': pt * pr,
                'observedPairAttempts': sum(e['receiver'] == NODES[b][0] for e in t)}

    def junctions(path):
        result = []
        for a, b, c in zip(path, path[1:], path[2:]):
            incoming = [e for e in throws[a, b] if e['complete']]
            outgoing = throws[b, c]
            distances = [min(math.hypot(e['rx']-f['tx'], e['ry']-f['ty']) for f in outgoing) for e in incoming] if outgoing else []
            result.append({'node': b, 'incomingCompletions': len(incoming),
                'medianNearestReleaseYards': statistics.median(distances) if distances else None,
                'landingsWithin5Yards': sum(d <= 5 for d in distances),
                'landingsWithin10Yards': sum(d <= 10 for d in distances)})
        return result

    def closest_template(path):
        """One illustrative chain of completed throws, minimizing release gaps.

        This is a geometric existence check, not a real possession, likelihood,
        or proof that the assigned receivers would have been available.
        """
        groups = [[e for e in throws[a, b] if e['complete'] and
                   (not terminal(b) or e['goal'])] for a, b in zip(path, path[1:])]
        if any(not group for group in groups):
            return None
        frontier = [(0., 0., [e], []) for e in groups[0]]
        for group in groups[1:]:
            following = []
            for nxt in group:
                options = []
                for worst, total, chosen, gaps in frontier:
                    prior = chosen[-1]
                    gap = math.hypot(prior['rx']-nxt['tx'], prior['ry']-nxt['ty'])
                    options.append((max(worst, gap), total+gap, chosen+[nxt], gaps+[gap]))
                following.append(min(options, key=lambda item: (item[0], item[1])))
            frontier = following
        worst, total, chosen, gaps = min(frontier, key=lambda item: (item[0], item[1]))
        return {'maxGapYards': worst, 'totalGapYards': total, 'gapsYards': gaps,
                'throws': [{k: e[k] for k in ('id', 'game', 'thrower', 'receiver', 'tx', 'ty', 'rx', 'ry', 'aec', 'goal')} for e in chosen]}

    def describe(path, strength=40):
        edges = [edge(a, b, strength) for a, b in zip(path, path[1:])]
        contributions = [{'node': n, 'player': NODES[n][0],
                          'role': 'Receiver' if terminal(n) else 'Thrower',
                          'aec': box_totals[n][NODES[n][0]]} for n in path]
        return {'nodes': path, 'names': [people[NODES[n][0]] for n in path],
                'overallBoxAec': math.fsum(c['aec'] for c in contributions),
                'boxAecContributions': contributions,
                'screenIndex': math.prod(e['screenIndex'] for e in edges),
                'passes': edges, 'junctions': junctions(path),
                'closestTemplate': closest_template(path)}

    def search(min_t=5, min_c=3, games=3, strength=40):
        routes = []
        def visit(path):
            if terminal(path[-1]):
                routes.append(describe(path, strength))
                return
            if len(path) == 5:
                return
            a = path[-1]
            for b, (pid, _name, _x, y) in NODES.items():
                if y <= NODES[a][3] or any(NODES[n][0] == pid for n in path):
                    continue
                t, c = throws[a, b], catches[a, b]
                if len(t) < min_t or len(c) < min_c:
                    continue
                if len({e['game'] for e in t}) < games or len({e['game'] for e in c}) < games:
                    continue
                visit(path + [b])
        visit(['init'])
        return sorted(routes, key=lambda r: r['screenIndex'], reverse=True)

    routes = search()
    # Keep five distinct ordered player chains; preserve the best box route
    # when the same player leads more than one box.
    top, seen = [], set()
    for route in routes:
        key = tuple(route['names'])
        if key not in seen:
            top.append(route)
            seen.add(key)
        if len(top) == 5:
            break
    assert len(top) == 5
    for r in routes:
        assert len(r['names']) == len(set(r['names']))
        assert math.isclose(r['screenIndex'], math.prod(e['screenIndex'] for e in r['passes']))
    comparisons = [describe(['init', 'goal-right']),
                   describe(['init', 'right-build', 'attack', 'red', 'goal-left'])]
    record = {
        'snapshotCapturedAt': '2026-09-29T16:19:13.770251+00:00',
        'reportingPeriod': [min(e['date'] for e in rows), max(e['date'] for e in rows)],
        'population': {'throws': len(rows), 'games': len({e['game'] for e in rows})},
        'nodes': {n: {'player': v[0], 'name': people[v[0]], 'label': v[1],
                       'x': v[2], 'y': v[3], 'boxAec': box_totals[n][v[0]]} for n, v in NODES.items()},
        'method': {
            'question': 'Connect the exact offensive box leaders in the supplied screenshot into hypothetical scoring sequences, starting with Atkins in central initiation.',
            'eligibility': 'One to four passes; forward by box-center y; no repeated player; at least five thrower attempts and three receiver targets in the exact source/destination boxes, each across at least three games. Keep the highest-index box route for each distinct ordered player chain.',
            'ranking': 'Product of thrower delivery and receiver catch rates per lane, each shrunk toward that league lane using 40 pseudo-observations. Terminal success requires the explicit goal marker. This is an uncalibrated in-sample screening index, not a predicted scoring probability or aEC.',
            'overallBoxAec': 'Combined box aEC is the sum of the unrounded 2026 regular-season aEC totals for the selected player in each selected box: thrower aEC for intermediate boxes and receiver aEC for the final end-zone box. It is a season aggregate, not an observed or predicted aEC for one possession. It does not change the candidate ordering.',
            'spatialCheck': 'For each intermediate box, compare the incoming thrower\'s completed landing points to the next thrower\'s recorded releases toward the next box. Nearest distances are diagnostics, not additional passes or feasibility probabilities.',
            'limitations': [
                'The hypothetical cross-team passes were not jointly observed; statistics describe each player with their actual teammates.',
                'Broad-box rates do not enforce identical catch/release points, getting open, pressure, clock, chemistry, or exact starting location.',
                'Sample floors, shrinkage and the four-pass limit affect the shortlist. The candidates are not an established league top five.',
                'Combined box aEC adds season totals from different possessions; longer routes can have larger totals because they include more boxes. It must not be read as a single-possession value or a measure of route efficiency. Observed event aEC belongs to its original possession context.',
                'A screenshot box indicates total seasonal contribution and includes players with different usage and line roles.',
                'One listed regular-season game, Pittsburgh at Chicago on July 18, has no source throws.'
            ],
        },
        'eligibleRoutes': len(routes), 'topFive': top, 'userExamples': comparisons,
        'sensitivity': {str(k): [r['nodes'] for r in search(strength=k)[:5]] for k in (10, 20, 80)},
        'stricterSampleEligibleRoutes': len(search(min_t=10, min_c=5)),
        'relaxedSampleTopFive': [r['nodes'] for r in search(min_t=2, min_c=1, games=1)[:5]],
    }
    (OUT / 'box_possessions.json').write_text(json.dumps(record, indent=2) + '\n')
    for i, r in enumerate(top, 1):
        print(i, ' → '.join(NODES[n][1] for n in r['nodes']), r['nodes'], round(r['screenIndex'], 4))
        print('  junctions', r['junctions'])
    print('Eligible routes:', len(routes), '; stricter sample:', record['stricterSampleEligibleRoutes'])
    print('Sensitivity:', record['sensitivity'])


if __name__ == '__main__':
    main()
