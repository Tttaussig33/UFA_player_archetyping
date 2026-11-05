"""Reconstruct receiving-team possessions, retaining zero-throw outcomes.

Read-only source inputs. A possession is a continuous spell with the disc;
team possession numbers do not reset when a timeout filter removes a row.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / 'data/database-exports/2026-10-12'
RAW = ROOT.parent / 'dead_disc_study/raw_events'
sys.path.insert(0, str(ROOT.parent / 'dead_disc_study'))
from audit_restarts import matched, number

ATTEMPTS = {18, 19, 20, 22, 23, 24}
PHYSICAL = ATTEMPTS - {24}
GAINS = {11, 13, 14}
PERIOD_ENDS = {28, 29, 30, 31, 32, 33}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_csv(name):
    with (SOURCE / (name + '.csv')).open(newline='') as f:
        yield from csv.DictReader(f)

def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def main():
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for name in ['throws', 'games', 'teams']:
        assert sha(SOURCE / (name + '.csv')) == manifest['tables'][name]['sha256']
    games = {g['GameID']: g for g in read_csv('games') if g['Year'] == '2026'
             and g['RegularSeasonWeek'] and not g['PlayoffRound'] and g['is_final'] == 'true'}
    names = {r['TeamID']: r['FullName'] for r in read_csv('teams') if r['Year'] == '2026'}
    stored = {}
    context_throws = defaultdict(list)
    for r in read_csv('throws'):
        if r['GameID'] not in games:
            continue
        key = (r['GameID'], r['source_side'], int(r['source_side_idx']))
        assert key not in stored
        stored[key] = r
        context_throws[(r['GameID'], r['source_side'], r['game_quarter'], r['quarter_point'])].append(r)
    receipts = json.loads((RAW / 'source_receipt.json').read_text())
    ambiguous = {tuple(r['context']) for r in json.loads(
        (ROOT.parent / 'pull_centering_study/results.json').read_text())['duplicate_opening_contexts']}
    points = []
    checks = Counter()
    source_scores = []
    for gid, game in sorted(games.items()):
        path = RAW / (gid + '.json')
        if not path.exists():
            assert gid == '2026-07-18-PIT-CHI'
            checks['missing_games'] += 1
            continue
        assert sha(path) == receipts[gid]['sha256']
        raw = json.loads(path.read_text())['data']
        for side in ['home', 'away']:
            es = raw[side + 'Events']
            own_goals = sum(e['type'] in {19, 12} for e in es)
            other_goals = sum(e['type'] in {15, 23} for e in es)
            source_scores.append({'game': gid, 'side': side, 'own_event_goals': own_goals,
                'opponent_event_goals': other_goals,
                'final_own_score': int(game['HomeScore' if side == 'home' else 'AwayScore']),
                'final_opponent_score': int(game['AwayScore' if side == 'home' else 'HomeScore'])})
            team = game['HomeTeamID' if side == 'home' else 'AwayTeamID']
            opponent = game['AwayTeamID' if side == 'home' else 'HomeTeamID']
            point = pos = None
            quarter = 1
            def new_pos(idx, typ):
                return {'id': point['id'] + '|' + str(len(point['possessions']) + 1),
                        'number': len(point['possessions']) + 1, 'start_idx': idx,
                        'start_type': typ, 'attempts': [], 'timeouts': [], 'injuries': [],
                        'penalties': [], 'end': None, 'end_idx': None,
                        'prior_timeout': bool(point['timeouts']), 'prior_injury': bool(point['injuries'])}
            for idx, e in enumerate(es):
                typ = e['type']
                if typ in {1, 2}:
                    if point is not None:
                        point['errors'].add('missing_point_end_before_next_start')
                    point = pos = None
                    if typ == 2:
                        point = {'id': f'{gid}|{side}|{idx}', 'GameID': gid, 'source_side': side,
                                 'team': team, 'opponent': opponent, 'start_idx': idx,
                                 'quarter': quarter, 'start_time': e.get('time'),
                                 'errors': set(), 'possessions': [], 'timeouts': [], 'injuries': [],
                                 'turnovers': 0, 'end': None, 'hold': None, 'end_idx': None}
                        points.append(point)
                        pos = new_pos(idx, typ)
                        point['possessions'].append(pos)
                    continue
                if point is not None:
                    if typ in {3, 5}:
                        point['timeouts'].append(idx)
                        if pos is not None: pos['timeouts'].append(idx)
                    elif typ == 25:
                        point['injuries'].append(idx)
                        if pos is not None: pos['injuries'].append(idx)
                    elif typ in {16, 17}:
                        if pos is not None: pos['penalties'].append(idx)
                    elif typ in GAINS:
                        if pos is not None or point['turnovers'] == 0:
                            point['errors'].add('gain_without_recorded_own_loss')
                        point['turnovers'] += 1
                        pos = new_pos(idx, typ)
                        point['possessions'].append(pos)
                    elif typ == 21:
                        if pos is None: point['errors'].add('dropped_pull_without_possession')
                        else: pos.update(end='turnover', end_type=21, end_idx=idx)
                        point['turnovers'] += 1
                        pos = None
                    elif typ in ATTEMPTS:
                        if pos is None:
                            point['errors'].add('attempt_without_possession_start')
                            continue
                        r = stored.get((gid, side, idx))
                        ordinal = len(pos['attempts']) + 1
                        if r is None or not matched(r, e):
                            point['errors'].add('missing_or_changed_export_attempt')
                        else:
                            context = tuple(r[k] for k in ['GameID', 'source_side', 'game_quarter', 'quarter_point'])
                            if context in ambiguous: point['errors'].add('duplicate_opening_context')
                            if r['start_on_offense'] != 'true': point['errors'].add('receiving_role_mismatch')
                            if number(r['possession_throw']) != ordinal: point['errors'].add('throw_ordinal_mismatch')
                            if number(r['possession_num']) != point['turnovers'] + 1: point['errors'].add('possession_number_mismatch')
                            if number(r['turnover']) != int(typ in {20, 22, 23, 24}): point['errors'].add('turnover_flag_mismatch')
                            if number(r['DroppedThrow']) != int(typ == 20): point['errors'].add('drop_flag_mismatch')
                            if number(r['stall']) != int(typ == 24): point['errors'].add('stall_flag_mismatch')
                            xy = [number(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
                            if typ != 24:
                                if any(v is None for v in xy): point['errors'].add('missing_coordinates')
                                elif not (abs(xy[0]) <= 26.67000001 and abs(xy[2]) <= 26.67000001 and 0 <= xy[1] <= 120 and 0 <= xy[3] <= 120):
                                    point['errors'].add('coordinates_outside_field')
                        pos['attempts'].append({'row': r, 'event': e, 'idx': idx})
                        if typ in {20, 22, 24}:
                            pos.update(end='turnover', end_type=typ, end_idx=idx)
                            point['turnovers'] += 1
                            pos = None
                        elif typ in {19, 23}:
                            pos.update(end='goal' if typ == 19 else 'turnover', end_type=typ, end_idx=idx)
                            point.update(end='goal', hold=int(typ == 19), end_idx=idx)
                            pos = point = None
                    elif typ == 12:
                        if pos is not None: point['errors'].add('callahan_while_own_possession_active')
                        pos = new_pos(idx, typ)
                        pos.update(end='goal', end_type=12, end_idx=idx)
                        point['possessions'].append(pos)
                        point.update(end='goal', hold=1, end_idx=idx)
                        pos = point = None
                    elif typ == 15:
                        if pos is not None: point['errors'].add('opponent_score_while_own_possession_active')
                        point.update(end='goal', hold=0, end_idx=idx)
                        pos = point = None
                    elif typ in PERIOD_ENDS:
                        if pos is not None: pos.update(end='period_end', end_type=typ, end_idx=idx)
                        point.update(end='period_end', hold=0, end_idx=idx)
                        pos = point = None
                    elif typ not in {4, 6, 9, 10, 26, 27}:
                        point['errors'].add('unhandled_event_' + str(typ))
                if typ in PERIOD_ENDS:
                    quarter = typ - 26
            if point is not None: point['errors'].add('unclosed_point_at_end_of_source')

    throws, possessions, point_rows, excluded = [], [], [], []
    for point in points:
        if point['errors']:
            excluded.append({'point_id': point['id'], 'reasons': sorted(point['errors'])})
            checks.update('point_error_' + e for e in point['errors'])
            continue
        checks['included_points'] += 1
        prior_own = 0
        for pos in point['possessions']:
            assert pos['end'] is not None, pos['id']
            rr = []
            for a in pos['attempts']:
                r, e = a['row'], a['event']
                if e['type'] == 24:
                    checks['stalls'] += 1
                    continue
                xy = [float(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
                distance = math.hypot(xy[2] - xy[0], xy[3] - xy[1])
                forward = xy[3] - xy[1]
                rr.append({'GameID': point['GameID'], 'team': point['team'], 'opponent': point['opponent'],
                           'point_id': point['id'], 'possession_id': pos['id'], 'own_possession': pos['number'],
                           'regained': int(pos['number'] > 1), 'ordinal': len(rr) + 1,
                           'source_side': point['source_side'], 'source_side_idx': a['idx'],
                           'quarter': int(r['game_quarter']), 'quarter_point': int(float(r['quarter_point'])),
                           'Thrower': r['Thrower'], 'Receiver': r['Receiver'], 'source_event_type': e['type'],
                           'tx': xy[0], 'ty': xy[1], 'rx': xy[2], 'ry': xy[3],
                           'huck': int(distance > 40 and forward > 30), 'vertical_huck': int(forward > 40),
                           'complete': int(e['type'] in {18, 19}), 'drop': int(e['type'] == 20),
                           'assist': int(e['type'] == 19), 'cp': number(r['cp'])})
            first = pos['attempts'][0]['row'] if pos['attempts'] else None
            first_x = number(first['ThrowerX']) if first else None
            first_y = number(first['ThrowerY']) if first else None
            prior_other = None
            if first:
                opposite = 'away' if point['source_side'] == 'home' else 'home'
                key = (point['GameID'], opposite, first['game_quarter'], first['quarter_point'])
                opposing = context_throws.get(key, [])
                # Only a unique opposite-side point start with matching period/time
                # certifies the cross-side context used for prior-activity counts.
                opposite_raw = json.loads((RAW / (point['GameID'] + '.json')).read_text())['data'][opposite + 'Events']
                q = 1; matches = []
                for i, e in enumerate(opposite_raw):
                    if e['type'] == 1 and q == point['quarter'] and e.get('time') == point['start_time']:
                        matches.append(i)
                    if e['type'] in PERIOD_ENDS: q = e['type'] - 26
                if len(matches) == 1:
                    st = matches[0]
                    en = next((i for i in range(st+1, len(opposite_raw)) if opposite_raw[i]['type'] in {1,2}|PERIOD_ENDS), len(opposite_raw))
                    previous = [r for r in opposing if number(r['possession_num']) < 2*pos['number']-1]
                    if all(st < int(r['source_side_idx']) < en for r in previous):
                        # Matching point labels alone is insufficient: an empty
                        # export context would otherwise look like zero activity.
                        # Independently walk the opponent's losses to this regain.
                        prior_indices = []
                        losses = 0
                        for oi in range(st+1, en):
                            if losses == pos['number']-1: break
                            oe = opposite_raw[oi]
                            if oe['type'] in {12,15,19,23}: break
                            if oe['type'] in PHYSICAL: prior_indices.append(oi)
                            if oe['type'] in {20,22,24}: losses += 1
                        exported_indices = [int(r['source_side_idx']) for r in previous
                                            if int(r['source_event_type']) in PHYSICAL]
                        if (losses == pos['number']-1 and prior_indices == sorted(exported_indices)
                            and all(matched(stored[(point['GameID'],opposite,oi)],opposite_raw[oi])
                                    for oi in prior_indices)):
                            prior_other = len(prior_indices)
            rec = {'GameID': point['GameID'], 'team': point['team'], 'team_name': names[point['team']],
                   'opponent': point['opponent'], 'point_id': point['id'], 'possession_id': pos['id'],
                   'quarter': point['quarter'], 'point_start_time': point['start_time'],
                   'own_possession': pos['number'], 'stage': min(pos['number'], 3),
                   'regained': int(pos['number'] > 1), 'start_type': pos['start_type'],
                   'start_idx': pos['start_idx'], 'end_idx': pos['end_idx'], 'end_type': pos['end_type'],
                   'outcome': pos['end'], 'goal': int(pos['end'] == 'goal'),
                   'throws': len(rr), 'hucks': sum(t['huck'] for t in rr),
                   'has_huck': int(any(t['huck'] for t in rr)),
                   'early_huck': int(any(t['huck'] and t['ordinal'] <= 3 for t in rr)),
                   'first_huck': next((t['ordinal'] for t in rr if t['huck']), None),
                   'first_x': first_x, 'first_y': first_y,
                   'has_timeout': bool(pos['timeouts']), 'has_injury': bool(pos['injuries']),
                   'has_penalty': bool(pos['penalties']),
                   'prior_timeout': pos['prior_timeout'], 'prior_injury': pos['prior_injury'],
                   'point_has_timeout': bool(point['timeouts']), 'point_has_injury': bool(point['injuries']),
                   'prior_own_throws': prior_own, 'prior_opponent_throws': prior_other,
                   'prior_total_throws': None if prior_other is None else prior_own + prior_other,
                   'point_hold': point['hold'], 'point_end': point['end']}
            for t in rr:
                for k in ['first_x','first_y','has_timeout','has_injury','prior_timeout','point_has_timeout','point_has_injury','stage']:
                    t[k] = rec[k]
                throws.append(t)
            possessions.append(rec)
            prior_own += len(rr)
        point_rows.append({'point_id': point['id'], 'GameID': point['GameID'], 'team': point['team'],
                           'hold': point['hold'], 'end': point['end'], 'own_possessions': len(point['possessions']),
                           'opening_outcome': point['possessions'][0]['end'],
                           'has_timeout': bool(point['timeouts']), 'has_injury': bool(point['injuries'])})
    p = pd.DataFrame(possessions)
    t = pd.DataFrame(throws)
    pts = pd.DataFrame(point_rows)
    assert not p.possession_id.duplicated().any()
    assert not t[['GameID','source_side','source_side_idx']].duplicated().any()
    assert int(p.throws.sum()) == len(t)
    assert p.groupby('point_id').own_possession.apply(lambda s: list(s) == list(range(1,len(s)+1))).all()
    assert p.groupby('point_id').goal.sum().le(1).all()
    assert p.groupby('point_id').goal.sum().eq(pts.set_index('point_id').hold).all()
    assert t.groupby('possession_id').ordinal.max().eq(p.set_index('possession_id').loc[t.possession_id.unique()].throws).all()
    p.to_csv(ROOT/'possessions.csv', index=False)
    t.to_csv(ROOT/'throws.csv', index=False)
    pts.to_csv(ROOT/'points.csv', index=False)
    mismatch = [r for r in source_scores if r['own_event_goals'] != r['final_own_score'] or r['opponent_event_goals'] != r['final_opponent_score']]
    audit = {'source_receiving_points': len(points), 'included_points': len(pts), 'excluded_points': excluded,
             'checks': dict(checks), 'games': p.GameID.nunique(), 'teams': p.team.nunique(),
             'possessions': len(p), 'physical_throws': len(t),
             'outcomes': p.outcome.value_counts().to_dict(),
             'zero_throw_outcomes': p[p.throws.eq(0)].outcome.value_counts().to_dict(),
             'score_reconciliation': {'team_streams_checked': len(source_scores), 'mismatches': mismatch},
             'timeouts': {'possessions_containing_timeout': int(p.has_timeout.sum()), 'later_possessions_after_timeout': int(p.prior_timeout.sum())},
             'prior_activity_missing_regains': int(p[p.regained.eq(1)].prior_total_throws.isna().sum()),
             'inputs': {name: manifest['tables'][name]['sha256'] for name in ['throws','games','teams']},
             'raw_source_receipt_sha256': sha(RAW/'source_receipt.json')}
    dump('cohort_audit.json', audit)
    print(json.dumps({k:v for k,v in audit.items() if k not in ['inputs','excluded_points','score_reconciliation']}, indent=2))
    print('Source score discrepancies:', len(mismatch))

if __name__ == '__main__':
    main()
