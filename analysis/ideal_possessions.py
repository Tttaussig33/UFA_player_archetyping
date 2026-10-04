"""Exploratory all-star routes from the preserved Shown Space snapshot.

This is a zone-level screening model, not a calibrated cross-team forecast.
Run with Python 3; no third-party dependencies or network access are required.
"""
from __future__ import annotations
import collections
import csv
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
ZONES = {
    'own': ('Own end zone', 10),
    'init': ('Central initiation', 30),
    'left-build': ('Left build-up', 40),
    'right-build': ('Right build-up', 40),
    'build': ('Central build-up', 50),
    'attack': ('Central attack', 70),
    'left-attack': ('Left attacking sideline', 80),
    'right-attack': ('Right attacking sideline', 80),
    'red': ('Central red zone', 90),
    'goal': ('Attacking end zone', 110),
}

def truth(value):
    return str(value).lower() in ('true', '1', '1.0')

def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None

def zone(x, y, terminal=False):
    if x is None or y is None or x < -26.670001 or x > 26.670001 or not 0 <= y <= 120:
        return None
    if terminal and y >= 100:
        return 'goal'
    if y > 100:
        return None
    if y < 20:
        return 'own'
    if x < -15:
        return 'left-build' if y < 60 else 'left-attack'
    if x >= 15:
        return 'right-build' if y < 60 else 'right-attack'
    return 'init' if y < 40 else 'build' if y < 60 else 'attack' if y < 80 else 'red'

def load():
    snapshot = json.loads((ROOT / 'src/data.json').read_text())
    manifest = json.loads((ROOT / 'data/source-manifest.json').read_text())
    games = {g['game']: g for g in snapshot['queries']['games']['rows']}
    reviewed = {e['id']: e for e in snapshot['queries']['events']['rows']}
    rows = []
    for item in manifest:
        path = ROOT / item['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        if path.suffix == '.csv':
            with path.open() as handle:
                source_rows = list(csv.DictReader(handle))
        else:
            source_rows = json.loads(path.read_text())['throws']
        assert len(source_rows) == item['rows']
        for index, raw in enumerate(source_rows):
            gid = raw['GameID']
            key = f"{gid}:{raw.get('throw_sig_id') or raw.get('event_sig_id') or index}"
            event = reviewed[key]
            assert number(raw.get('aec')) == event['aec']
            if event['phase'] != 'Regular season':
                continue
            row = dict(event)
            row.update({
                'point': int(float(raw['quarter_point'])),
                'possession': int(float(raw['possession_num'])),
                'order': int(float(raw['possession_throw'])),
                'goal': number(raw.get('source_event_type')) == 19,
                'cp': number(raw.get('cp')),
                'fv_start': number(raw.get('fv_thrower')),
                'fv_end': number(raw.get('fv_receiver')),
                'min_fv': number(raw.get('min_fv')),
            })
            row['start_zone'] = zone(row['tx'], row['ty'])
            row['end_zone'] = zone(row['rx'], row['ry'], row['goal'] or not row['complete'])
            rows.append(row)
    assert len(rows) == 72663
    assert len({r['id'] for r in rows}) == len(rows)
    return snapshot, rows

def new_stat():
    return {'n': 0, 'good': 0, 'games': set(), 'ids': [], 'tx': [], 'ty': [], 'rx': [], 'ry': []}

def add_stat(stat, row, good):
    stat['n'] += 1
    stat['good'] += int(good)
    stat['games'].add(row['game'])
    stat['ids'].append(row['id'])
    for key in ('tx', 'ty', 'rx', 'ry'):
        stat[key].append(row[key])

def fit(rows):
    throws = collections.defaultdict(new_stat)
    catches = collections.defaultdict(new_stat)
    base_throws = collections.defaultdict(new_stat)
    base_catches = collections.defaultdict(new_stat)
    excluded = 0
    for r in rows:
        s, d = r['start_zone'], r['end_zone']
        if s is None or d is None:
            excluded += 1
            continue
        delivery = r['complete'] or r['drop']
        for key, table in [((s, d), base_throws), ((r['thrower'], s, d), throws)]:
            add_stat(table[key], r, delivery)
        if r['receiver'] and r['receiver'] != 'unknown' and delivery:
            for key, table in [((s, d), base_catches), ((r['receiver'], s, d), catches)]:
                add_stat(table[key], r, r['complete'])
    return throws, catches, base_throws, base_catches, excluded

def beta_params(stat, base, strength):
    # A half-observation on each outcome keeps empirical priors away from 0/1.
    prior = (base['good'] + .5) / (base['n'] + 1)
    return stat['good'] + strength * prior, stat['n'] - stat['good'] + strength * (1 - prior)

def describe_stat(stat):
    return {'n': stat['n'], 'good': stat['good'], 'games': len(stat['games']),
            'meanStart': [statistics.mean(stat['tx']), statistics.mean(stat['ty'])],
            'meanEnd': [statistics.mean(stat['rx']), statistics.mean(stat['ry'])]}

def search(fitted, strength=40, max_passes=4, min_throws=20, min_targets=10):
    throws, catches, base_throws, base_catches, _ = fitted
    receivers = collections.defaultdict(list)
    for (player, s, d), stat in catches.items():
        if stat['n'] >= min_targets and len(stat['games']) >= 3:
            receivers[s, d].append((player, stat))
    choices = collections.defaultdict(list)
    for (player, s, d), stat in throws.items():
        if player == 'unknown' or stat['n'] < min_throws or len(stat['games']) < 3:
            continue
        if ZONES[d][1] <= ZONES[s][1]:
            continue
        tp = beta_params(stat, base_throws[s, d], strength)
        for receiver, rstat in receivers[s, d]:
            if player == receiver:
                continue
            rp = beta_params(rstat, base_catches[s, d], strength)
            p = tp[0] / sum(tp) * rp[0] / sum(rp)
            choices[player, s].append({'thrower': player, 'receiver': receiver, 'from': s, 'to': d,
                'p': p, 'throwBeta': tp, 'catchBeta': rp,
                'throwEvidence': describe_stat(stat), 'catchEvidence': describe_stat(rstat)})
    frontier = [(1., [p], []) for p, s in choices if s == 'init']
    finals = []
    for depth in range(max_passes):
        next_states = collections.defaultdict(list)
        for probability, people, path in frontier:
            start = path[-1]['to'] if path else 'init'
            for edge in choices[people[-1], start]:
                if edge['receiver'] in people:
                    continue
                updated = probability * edge['p'], people + [edge['receiver']], path + [edge]
                if edge['to'].startswith('goal'):
                    finals.append(updated)
                else:
                    next_states[edge['receiver'], edge['to']].append(updated)
        # Bounded search: retain 12 candidate histories per player/zone state.
        frontier = []
        for candidates in next_states.values():
            candidates.sort(key=lambda p: p[0], reverse=True)
            frontier.extend(candidates[:12])
    finals.sort(key=lambda p: p[0], reverse=True)
    return finals

def summarize_possessions(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row['game'], row['quarter'], row['point'], row['possession'], row['team']].append(row)
    goals, issues = [], collections.Counter()
    for key, path in groups.items():
        path.sort(key=lambda r: r['order'])
        if [r['order'] for r in path] != list(range(1, len(path) + 1)):
            issues['nonconsecutive_order'] += 1
            continue
        if any(r['aec'] is None for r in path):
            issues['missing_aec'] += 1
            continue
        if any(not r['complete'] or r['goal'] for r in path[:-1]):
            issues['early_terminal_event'] += 1
            continue
        if path[-1]['goal'] and path[-1]['complete']:
            goals.append({'key': list(key), 'passes': len(path), 'aec': sum(r['aec'] for r in path),
                          'startY': path[0]['ty'], 'people': [path[0]['thrower']] + [r['receiver'] for r in path]})
    return {'possessions': len(groups), 'excluded': dict(issues), 'verified_goal_endings': len(goals),
            'median_goal_aec': statistics.median(g['aec'] for g in goals),
            'goal_aec_p10': sorted(g['aec'] for g in goals)[int(len(goals)*.1)],
            'goal_aec_p90': sorted(g['aec'] for g in goals)[int(len(goals)*.9)],
            'top_raw_sums': sorted(goals, key=lambda p: p['aec'], reverse=True)[:5]}

def main():
    snapshot, rows = load()
    fitted = fit(rows)
    finals = search(fitted)
    assert finals
    # Different ordered player chains; changing only the finishing box is one route.
    seen, selected = set(), []
    for route in finals:
        key = tuple(route[1])
        if key not in seen:
            selected.append(route)
            seen.add(key)
        if len(selected) == 5:
            break
    people = {p['id']: p['name'] for p in snapshot['queries']['players']['rows']}
    teams = collections.defaultdict(collections.Counter)
    for row in rows:
        teams[row['thrower']][row['team']] += 1
        if row['receiver']:
            teams[row['receiver']][row['team']] += 1
    team_names = {t['id']: t['abbrev'] for t in snapshot['queries']['teams']['rows']}
    def player(p):
        return {'id': p, 'name': people.get(p, p), 'team': team_names[teams[p].most_common(1)[0][0]]}
    rng = random.Random(20261002)
    output_routes = []
    for index, (p, ids, edges) in enumerate(selected, 1):
        draws = sorted(math.prod(rng.betavariate(*edge['throwBeta']) * rng.betavariate(*edge['catchBeta']) for edge in edges) for _ in range(4000))
        output_routes.append({'rank': index, 'probability': p, 'interval90': [draws[200], draws[3799]],
                              'players': [player(pid) for pid in ids], 'passes': edges})
    sensitivity = {}
    for strength in (20, 80):
        candidates = search(fitted, strength=strength)
        sensitivity[str(strength)] = {'best_probability': candidates[0][0], 'best_players': [player(p) for p in candidates[0][1]]}
    best_by_length = []
    for n in range(1, 5):
        match = next((p for p in finals if len(p[2]) == n), None)
        if match:
            best_by_length.append({'passes': n, 'probability': match[0], 'players': [player(p) for p in match[1]], 'edges': match[2]})
    # Include sparse long-pass routes in a separate sensitivity search, rather
    # than mistaking their absence under the primary sample floor for inferiority.
    relaxed = search(fitted, min_throws=3, min_targets=3)
    relaxed_by_length = []
    for n in range(1, 5):
        match = next((p for p in relaxed if len(p[2]) == n), None)
        if match:
            draws = sorted(math.prod(rng.betavariate(*edge['throwBeta']) * rng.betavariate(*edge['catchBeta']) for edge in match[2]) for _ in range(4000))
            relaxed_by_length.append({'passes': n, 'probability': match[0], 'interval90': [draws[200], draws[3799]],
                'players': [player(p) for p in match[1]], 'edges': match[2]})
    result = {
        'snapshotCapturedAt': snapshot['generatedAt'], 'season': '2026 regular season',
        'games': len({r['game'] for r in rows}), 'throws': len(rows),
        'sourceManifest': 'data/source-manifest.json',
        'method': {'start': 'Central initiation: x in [-15,15), y in [20,40)',
                   'maxPasses': 4, 'minimumThrowerAttemptsPerEdge': 20, 'minimumReceiverTargetsPerEdge': 10,
                   'minimumGamesPerRoleEdge': 3, 'priorStrength': 40,
                   'objective': 'Product of shrunk thrower delivery and receiver catch rates across the route.',
                   'terminal': 'All attacking end-zone boxes pooled: recorded event type 19 goals, plus attempted end-zone passes on turnovers.',
                   'constraints': 'Forward zone-center progress; no repeated player; 12 retained histories per player/zone state.',
                   'uncertainty': '90% conditional Beta posterior interval; does not cover model misspecification or cross-team chemistry.',
                   'limitations': ['Exploratory in-sample screening, not a calibrated forecast or a claim of a global tactical optimum.',
                                   'Broad spatial zones do not fix exact throw distance, marking pressure, weather, receiver separation, or timing.',
                                   'Adjacent-zone historical throws often cross only part of a band; linking zone averages can overstate spatial progress. No exact continuous field path is estimated.',
                                   'Thrower delivery and receiver catching are factored independently; fit together only in this hypothetical model.',
                                   'Receiver exposure excludes untargeted throwaways; off-disc creation and ability to get open are not measured.',
                                   'One regular-season game lacks throw data; playoffs excluded.']},
        'possessionAudit': summarize_possessions(rows), 'excludedUnmappedThrows': fitted[-1],
        'candidateRoutes': len(finals), 'topFive': output_routes,
        'bestByPassCount': best_by_length, 'priorSensitivity': sensitivity,
        'relaxedSearch': {'minimumAttemptsAndTargets': 3, 'minimumGames': 3,
                          'candidateRoutes': len(relaxed), 'bestByPassCount': relaxed_by_length},
    }
    OUT.mkdir(exist_ok=True)
    (OUT / 'ideal_possessions.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ('games','throws','candidateRoutes','possessionAudit','priorSensitivity')}, indent=2))
    for r in output_routes:
        print(r['rank'], round(r['probability']*100, 2), [round(v*100,1) for v in r['interval90']], ' -> '.join(p['name'] for p in r['players']), ' / '.join(e['to'] for e in r['passes']))
    print('BY LENGTH')
    for r in best_by_length:
        print(r['passes'], round(r['probability']*100, 2), ' -> '.join(p['name'] for p in r['players']))

if __name__ == '__main__':
    main()
