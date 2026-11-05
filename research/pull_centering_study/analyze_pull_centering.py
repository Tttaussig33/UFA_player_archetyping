"""Find the first completed inward pass of each recorded receiving possession.

Counts observed disc geometry, not a video-confirmed centering play or cut.
Player identity is attributed to the team in that game, never a current roster.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'dead_disc_study'))
from audit_restarts import SOURCE, RAW, read_csv, number, matched, sha, write_csv

ATTEMPTS = {18, 19, 20, 22, 23, 24}
END_CONTEXT = {1, 4, 6, 7, 8, 11, 12, 13, 14, 15, 21, 28, 29, 30, 31, 32, 33, 34, 35}
CONTINUE_CONTEXT = {3, 5, 9, 10, 16, 17, 25, 26, 27}
MISSING_ID = {'', 'unknown', 'none', 'null', 'nan'}


def main():
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for name in ['throws', 'games', 'players', 'teams']:
        assert sha(SOURCE / (name + '.csv')) == manifest['tables'][name]['sha256']
    games = {r['GameID']: r for r in read_csv('games') if r['Year'] == '2026'
             and r['RegularSeasonWeek'] and not r['PlayoffRound'] and r['is_final'].lower() == 'true'}
    teams = {r['TeamID']: r for r in read_csv('teams') if r['Year'] == '2026'}
    names = {}
    for p in read_csv('players'):
        if p['Year'] == '2026':
            label = ' '.join(p['full_name'].split())
            if p['PlayerID'] in names:
                assert names[p['PlayerID']] == label
            names[p['PlayerID']] = label
    grouped = defaultdict(list)
    keys = set()
    for r in read_csv('throws'):
        if r['GameID'] in games:
            key = (r['GameID'], r['throw_sig_id'])
            assert key not in keys
            keys.add(key)
            grouped[r['GameID']].append(r)
    receipts = json.loads((RAW / 'source_receipt.json').read_text())
    opening_sequences = []
    checks = Counter()
    for gid, rows in sorted(grouped.items()):
        raw_path = RAW / (gid + '.json')
        assert sha(raw_path) == receipts[gid]['sha256']
        raw = json.loads(raw_path.read_text())['data']
        lookups = {}
        for r in rows:
            side, idx = r['source_side'], int(r['source_side_idx'])
            evs = raw[side + 'Events']
            ev = evs[idx] if 0 <= idx < len(evs) else {}
            if matched(r, ev):
                assert (side, idx) not in lookups
                lookups[(side, idx)] = r
                checks['matched_source_throws'] += 1
            else:
                checks['unmatched_source_throws'] += 1
        for side in ['home', 'away']:
            current = None
            team = games[gid]['HomeTeamID' if side == 'home' else 'AwayTeamID']
            for i, e in enumerate(raw[side + 'Events']):
                typ = e['type']
                if typ == 2:
                    current = {'id': gid + ':' + side + ':' + str(i), 'GameID': gid,
                               'source_side': side, 'start_index': i, 'TeamID': team,
                               'attempts': [], 'errors': [], 'intervening_markers': []}
                    opening_sequences.append(current)
                    checks['receiving_point_start_markers'] += 1
                elif typ in END_CONTEXT:
                    if current is not None:
                        current['end_event_type'] = typ
                    current = None
                elif typ in CONTINUE_CONTEXT:
                    if current is not None:
                        current['intervening_markers'].append({'index': i, 'type': typ})
                elif typ in ATTEMPTS:
                    if current is not None:
                        ordinal = len(current['attempts']) + 1
                        r = lookups.get((side, i))
                        if r is None:
                            current['errors'].append('unmatched_source_attempt')
                            current['attempts'].append({'source_side_idx': i, 'ordinal': ordinal, 'matched': False})
                        else:
                            xy = [number(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
                            valid_geometry = (all(x is not None for x in xy)
                                              and abs(xy[0]) <= 26.67000001 and abs(xy[2]) <= 26.67000001
                                              and 0 <= xy[1] <= 120 and 0 <= xy[3] <= 120)
                            if number(r['possession_num']) != 1 or r['start_on_offense'].lower() != 'true':
                                current['errors'].append('opening_possession_metadata_disagrees')
                            if number(r['possession_throw']) != ordinal:
                                current['errors'].append('throw_order_metadata_disagrees')
                            if r['is_home_team'].lower() != ('true' if side == 'home' else 'false'):
                                current['errors'].append('team_side_disagrees')
                            if (typ in {18, 19}) != (number(r['turnover']) == 0):
                                current['errors'].append('completion_flag_disagrees')
                            distance = math.hypot(xy[2] - xy[0], xy[3] - xy[1]) if valid_geometry else None
                            current['attempts'].append({
                                'matched': True, 'source_side_idx': i, 'ordinal': ordinal,
                                'throw_sig_id': r['throw_sig_id'], 'Thrower': r['Thrower'], 'Receiver': r['Receiver'],
                                'quarter': r['game_quarter'], 'point': r['quarter_point'],
                                'source_event_type': typ, 'complete': number(r['turnover']) == 0,
                                'stall': number(r['stall']) == 1, 'valid_geometry': valid_geometry,
                                'tx': xy[0], 'ty': xy[1], 'rx': xy[2], 'ry': xy[3],
                                'inward_yards': abs(xy[0]) - abs(xy[2]) if valid_geometry else None,
                                'project_huck': bool(valid_geometry and distance > 40 and xy[3] - xy[1] > 30),
                            })
                        if typ in {19, 20, 22, 23, 24}:
                            current['end_event_type'] = typ
                            current = None
                else:
                    if current is not None:
                        current['errors'].append('unrecognized_raw_event')
                    current = None
    # Repeated Start O markers can describe the same point twice. Without video
    # we cannot choose which opening sequence is genuine, so exclude both.
    context_sequences = defaultdict(list)
    for seq in opening_sequences:
        contexts = {(a['quarter'], a['point']) for a in seq['attempts'] if a['matched']}
        if len(contexts) == 1:
            quarter, point = next(iter(contexts))
            context_sequences[(seq['GameID'], seq['source_side'], quarter, point)].append(seq)
    duplicate_contexts = []
    for context, sequences in context_sequences.items():
        if len(sequences) > 1:
            duplicate_contexts.append({'context': list(context), 'sequence_ids': [s['id'] for s in sequences]})
            for seq in sequences:
                seq['errors'].append('duplicate_opening_point_context')
    variants = {
        'any_inward': lambda a: a['inward_yards'] > 1e-6,
        'at_least_5_yards': lambda a: a['inward_yards'] >= 5 - 1e-6,
        'any_inward_excluding_hucks': lambda a: a['inward_yards'] > 1e-6 and not a['project_huck'],
    }
    selected = {k: [] for k in variants}
    coverage = defaultdict(Counter)
    excluded = []
    for seq in opening_sequences:
        cov = coverage[seq['TeamID']]
        cov['receiving_point_starts'] += 1
        if not seq['attempts']:
            cov['no_recorded_initial_attempt'] += 1
            continue
        contexts = {(a['quarter'], a['point']) for a in seq['attempts'] if a['matched']}
        if len(contexts) > 1:
            seq['errors'].append('point_context_changes')
        if any(a.get('complete') and not a.get('valid_geometry') for a in seq['attempts']):
            seq['errors'].append('unknown_geometry_in_completed_pass')
        if seq['errors']:
            cov['excluded_unreliable_sequences'] += 1
            excluded.append({'id': seq['id'], 'TeamID': seq['TeamID'], 'errors': sorted(set(seq['errors']))})
            continue
        cov['verified_opening_possessions'] += 1
        for key, predicate in variants.items():
            candidates = [a for a in seq['attempts'] if a['complete'] and not a['stall']
                          and a['valid_geometry'] and predicate(a)]
            if not candidates:
                continue
            a = candidates[0]
            row = {'variant': key, 'sequence_id': seq['id'], 'GameID': seq['GameID'],
                   'TeamID': seq['TeamID'], 'source_side': seq['source_side'], 'start_index': seq['start_index'], **a}
            selected[key].append(row)
    summaries = {}
    all_player_records = []
    for variant, rows in selected.items():
        counts = Counter((r['TeamID'], r['Receiver']) for r in rows if r['Receiver'].lower() not in MISSING_ID)
        totals = Counter(r['TeamID'] for r in rows)
        unknown = Counter(r['TeamID'] for r in rows if r['Receiver'].lower() in MISSING_ID)
        table = []
        for tid, team in sorted(teams.items(), key=lambda item: item[1]['FullName']):
            ranked = sorted([(pid, n) for (t, pid), n in counts.items() if t == tid], key=lambda z: (-z[1], z[0]))
            top = ranked[0][1] if ranked else 0
            leaders = [{'PlayerID': pid, 'name': names.get(pid, pid), 'count': n} for pid, n in ranked if n == top]
            game_count = sum(tid in {g['HomeTeamID'], g['AwayTeamID']} for gid, g in games.items() if gid in grouped)
            table.append({'TeamID': tid, 'team': team['FullName'], 'abbrev': team['Abbrev'],
                          'games': game_count, 'leaders': leaders, 'leader_count': top,
                          'qualifying_centering_passes': totals[tid], 'unattributed_centering_passes': unknown[tid],
                          'leader_share': top / totals[tid] if totals[tid] else None,
                          'coverage': dict(coverage[tid])})
            for pid, n in ranked:
                all_player_records.append({'variant': variant, 'TeamID': tid, 'team': team['FullName'],
                                           'PlayerID': pid, 'name': names.get(pid, pid), 'count': n,
                                           'team_centering_passes': totals[tid], 'share': n / totals[tid]})
        summaries[variant] = table
    for table in summaries.values():
        assert len(table) == 22 and all(r['leaders'] for r in table)
    changes = {}
    for variant in ['at_least_5_yards', 'any_inward_excluding_hucks']:
        changes[variant] = [a['team'] for a, b in zip(summaries['any_inward'], summaries[variant])
                            if {p['PlayerID'] for p in a['leaders']} != {p['PlayerID'] for p in b['leaders']}]
    result = {
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'scope': '2026 regular season, 131 of 132 games in the preserved ShownSpace export',
        'missing_game': '2026-07-18-PIT-CHI',
        'definition': 'Within the first receiving possession after a raw Start O Point event (type 2), select the earliest completed pass with abs(ReceiverX) < abs(ThrowerX). It may occur after another pass. Stop at a goal, turnover, possession change or period/point boundary. One selected pass per receiving possession.',
        'centering_measure': 'Reduction in absolute lateral distance from field centerline (yards). Geometry is an operational proxy, not a video-confirmed tactical label. A cross-field pass qualifies only if it finishes closer to center.',
        'denominator': 'The leader share is that player’s selected centering receptions divided by all selected centering receptions for the team. It is not a share of every pull or every reception.',
        'team_assignment': 'Game home/away team from the throw source side; roster is used only for display name.',
        'checks': dict(checks), 'excluded_sequences': excluded, 'duplicate_opening_contexts': duplicate_contexts,
        'coverage_totals': dict(sum(coverage.values(), Counter())),
        'selected_counts': {k: len(v) for k, v in selected.items()},
        'primary_pass_ordinal_counts': dict(Counter(str(r['ordinal']) for r in selected['any_inward'])),
        'primary_selected_hucks': sum(r['project_huck'] for r in selected['any_inward']),
        'leader_changes': changes, 'teams': summaries,
        'sources': {'export_manifest': str(SOURCE / 'manifest.json'), 'raw_events_receipt': str(RAW / 'source_receipt.json'),
                    'event_documentation': 'https://www.docs.ufastats.com/events'},
        'limitations': ['One regular-season game missing: Chicago and Pittsburgh have 11 games, other teams 12.',
                       'No minimum throwing distance, no CP filter, no skill inference. Dropped passes are not completed receptions.',
                       'The full first receiving possession is searched, including passes after a timeout or foul; the first centering pass may occur later than a pull play.',
                       'Sequences with conflicting metadata, missing source attempts, or unknown completed-pass geometry are excluded rather than skipping to a later pass.',
                       'Two opening sequences share the same Oakland point context on May 30; both are excluded because the genuine sequence cannot be established from these records alone.'],
    }
    (ROOT / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    (ROOT / 'selected_passes.json').write_text(json.dumps(selected, indent=2, allow_nan=False))
    write_csv(ROOT / 'player_counts.csv', all_player_records)
    flat = [{'team': r['team'], 'players': ' / '.join(p['name'] for p in r['leaders']),
             'count_each': r['leader_count'], 'team_centering_passes': r['qualifying_centering_passes'],
             'share_each': r['leader_share'], 'games': r['games']} for r in summaries['any_inward']]
    write_csv(ROOT / 'team_leaders.csv', flat)
    print(json.dumps({'checks': result['checks'], 'coverage': result['coverage_totals'],
                      'selected': result['selected_counts'], 'leader_changes': changes,
                      'primary_selected_hucks': result['primary_selected_hucks'], 'leaders': flat}, indent=2))


if __name__ == '__main__':
    main()
