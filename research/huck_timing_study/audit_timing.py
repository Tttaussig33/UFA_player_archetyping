"""Audit possession-stage measurements before estimating huck timing effects.

Reads preserved exports and source captures only. Does not query a live database,
change source values, estimate completion effects, or rank players.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/Users/teddytaussig/Desktop/Work/UFA_player_archetyping/data/database-exports/2026-10-12')
METADATA = SOURCE.parent.parent / 'database-metadata/2026-11-04'
RAW = ROOT.parent / 'dead_disc_study/raw_events'
sys.path.insert(0, str(ROOT.parent / 'dead_disc_study'))
from audit_restarts import matched

ATTEMPTS = {18, 19, 20, 22, 23, 24}
GAINS = {11, 13, 14}
TERMINALS = {19, 20, 22, 23, 24}
ENDS = {12, 15, 21, 28, 29, 30, 31, 32, 33, 34, 35}
POINT_FIELDS = ['GameID', 'source_side', 'game_quarter', 'quarter_point']


def number(x):
    try:
        n = float(x)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows(name):
    with (SOURCE / (name + '.csv')).open(newline='') as f:
        yield from csv.DictReader(f)


def key(row, fields=POINT_FIELDS):
    return tuple(row[k] for k in fields)


def is_huck(r):
    xy = [number(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
    if number(r['stall']) != 0 or any(n is None for n in xy):
        return False
    tx, ty, rx, ry = xy
    return (abs(tx) <= 26.67000001 and abs(rx) <= 26.67000001
            and 0 <= ty <= 120 and 0 <= ry <= 120
            and math.hypot(rx - tx, ry - ty) > 40 and ry - ty > 30)


def main():
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for name in ['games', 'throws']:
        assert sha(SOURCE / (name + '.csv')) == manifest['tables'][name]['sha256']
    games = {r['GameID'] for r in rows('games') if r['Year'] == '2026'
             and r['RegularSeasonWeek'] and not r['PlayoffRound'] and r['is_final'] == 'true'}
    throws = [r for r in rows('throws') if r['GameID'] in games]
    assert len({(r['GameID'], r['throw_sig_id']) for r in throws}) == len(throws)
    assert len({(r['GameID'], r['source_side'], r['source_side_idx']) for r in throws}) == len(throws)
    receipt = json.loads((RAW / 'source_receipt.json').read_text())
    raw = {}
    raw_field_counts = defaultdict(Counter)
    reconstructed = {}
    for gid in sorted(games):
        path = RAW / (gid + '.json')
        if not path.exists():
            continue
        assert sha(path) == receipt[gid]['sha256'], gid
        raw[gid] = json.loads(path.read_text())['data']
        for side in ['home', 'away']:
            ordinal, known_start, origin = 0, False, 'unverified'
            segment_start = None
            point_role, point_start = None, None
            prior_team_losses, point_turnovers, attack_number = 0, 0, 0
            lineup_change_marker = False
            for i, e in enumerate(raw[gid][side + 'Events']):
                typ = e['type']
                counts = raw_field_counts[str(typ)]
                counts['events'] += 1
                for field in ['time', 'timestamp']:
                    if number(e.get(field)) is not None:
                        counts[field] += 1
                if typ in {1, 2}:
                    ordinal, known_start = 0, typ == 2
                    origin = 'receiving_pull' if typ == 2 else 'unverified'
                    segment_start = i if typ == 2 else None
                    point_role = 'receiving' if typ == 2 else 'pulling'
                    point_start = i
                    prior_team_losses, point_turnovers = 0, 0
                    attack_number = int(typ == 2)
                    lineup_change_marker = False
                elif typ in GAINS:
                    ordinal, known_start, origin, segment_start = 0, True, 'turnover', i
                    point_turnovers += 1
                    attack_number += 1
                elif typ in ENDS:
                    ordinal, known_start, origin, segment_start = 0, False, 'unverified', None
                    if typ == 21:
                        prior_team_losses += 1
                        point_turnovers += 1
                    else:
                        point_role, point_start = None, None
                elif typ in {3, 5, 25}:
                    # A potential personnel change does not start a new possession.
                    lineup_change_marker = True
                elif typ in ATTEMPTS:
                    ordinal += 1
                    reconstructed[(gid, side, str(i))] = {
                        'ordinal': ordinal, 'known_start': known_start, 'origin': origin,
                        'segment_start': segment_start,
                        'point_role': point_role, 'point_start': point_start,
                        'prior_team_losses': prior_team_losses,
                        'prior_point_turnovers': point_turnovers,
                        'team_attack_number': attack_number,
                        'lineup_change_marker_before_throw': lineup_change_marker,
                    }
                    if typ in TERMINALS:
                        ordinal, known_start, origin, segment_start = 0, False, 'unverified', None
                        if typ in {20, 22, 24}:
                            prior_team_losses += 1
                            point_turnovers += 1
                        else:
                            point_role, point_start = None, None

    coverage = {}
    for field in ['PointStartTime', 'time_left', 'game_time_left', 'source_timestamp',
                  'derived_sort_timestamp', 'possession_num', 'possession_throw']:
        coverage[field] = sum(number(r[field]) is not None for r in throws)
    points, segments, possessions = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in throws:
        points[key(r)].append(r)
        possessions[key(r) + (r['possession_num'],)].append(r)
        if number(r['time_left']) is not None and number(r['PointStartTime']) is not None:
            segments[key(r) + (r['PointStartTime'],)].append(r)
    clock_counts = Counter()
    for group in segments.values():
        if len(group) < 3:
            continue
        group.sort(key=lambda r: int(r['source_side_idx']))
        clock_counts['segments_with_at_least_three_export_rows'] += 1
        gaps = [float(a['time_left']) - float(b['time_left']) for a, b in zip(group, group[1:])]
        if max(gaps) - min(gaps) < 1e-6:
            clock_counts['segments_with_equal_clock_spacing'] += 1
            clock_counts['rows_in_equal_spacing_segments'] += len(group)
            if all(number(r['source_timestamp']) is not None for r in group):
                clock_counts['equal_spacing_segments_with_complete_raw_timestamps'] += 1
                raw_gaps = [float(b['source_timestamp']) - float(a['source_timestamp'])
                            for a, b in zip(group, group[1:])]
                if max(raw_gaps) - min(raw_gaps) > 1e-6:
                    clock_counts['equal_clock_spacing_but_unequal_raw_timestamp_gaps'] += 1

    ordinal_counts, nonsequential = Counter(), []
    for k, group in possessions.items():
        group.sort(key=lambda r: int(r['source_side_idx']))
        ordinals = [number(r['possession_throw']) for r in group]
        ordinal_counts['export_possession_groups'] += 1
        if ordinals == list(range(1, len(group) + 1)):
            ordinal_counts['groups_sequential_from_one'] += 1
            ordinal_counts['rows_in_sequential_groups'] += len(group)
        else:
            nonsequential.append({'context': k, 'ordinals': ordinals})
    ambiguous = {tuple(r['context']) for r in json.loads(
        (ROOT.parent / 'pull_centering_study/results.json').read_text())['duplicate_opening_contexts']}
    source_check, huck_check, point_context_support = Counter(), Counter(), Counter()
    mismatch_examples = []
    eligible = []
    for r in throws:
        k = (r['GameID'], r['source_side'], r['source_side_idx'])
        events = raw.get(r['GameID'], {}).get(r['source_side'] + 'Events', [])
        idx = int(r['source_side_idx'])
        source_ok = 0 <= idx < len(events) and matched(r, events[idx])
        source_check['matched_export_rows' if source_ok else 'unmatched_export_rows'] += 1
        context = reconstructed.get(k)
        verified = bool(source_ok and context and context['known_start'])
        agrees = bool(verified and number(r['possession_throw']) == context['ordinal'])
        source_check['rows_with_explicit_source_possession_start'] += int(verified)
        source_check['rows_matching_source_throw_ordinal'] += int(agrees)
        if agrees and context['point_role'] is not None:
            source_check['rows_with_raw_point_role'] += 1
            expected_role = context['point_role'] == 'receiving'
            source_check['point_role_matches_start_on_offense'] += int((r['start_on_offense'] == 'true') == expected_role)
            source_check['point_turnovers_match_export_possession_num'] += int(number(r['possession_num']) == context['prior_point_turnovers'] + 1)
        if verified and not agrees and len(mismatch_examples) < 10:
            mismatch_examples.append({'key': k, 'stored': number(r['possession_throw']),
                                      'source_ordinal': context['ordinal']})
        if not is_huck(r) or key(r) in ambiguous or not source_ok:
            continue
        if number(r['turnover']) not in {0, 1} or number(r['DroppedThrow']) not in {0, 1}:
            continue
        if number(r['DroppedThrow']) == 1 and number(r['turnover']) != 1:
            continue
        huck_check['qualifying_hucks'] += 1
        huck_check['hucks_with_verified_source_start'] += int(verified)
        huck_check['hucks_with_matching_source_ordinal'] += int(agrees)
        huck_check['hucks_with_raw_timestamp'] += int(number(r['source_timestamp']) is not None)
        if agrees:
            eligible.append(r)
            role = context['point_role']
            if role is not None:
                phase = 'first_attacking_possession' if context['team_attack_number'] == 1 else 'later_attacking_possession'
                point_context_support[role + '_' + phase] += 1
                huck_check['hucks_with_raw_point_role'] += 1
                huck_check['hucks_after_potential_lineup_change'] += int(context['lineup_change_marker_before_throw'])
    assert huck_check['qualifying_hucks'] == json.loads(
        (ROOT.parent / 'repeatable_throwing_strengths/huck_feasibility.json').read_text())['by_year']['2026']['hucks']

    example = [r for r in throws if key(r) == ('2026-06-14-CHI-PIT', 'home', '1', '3')]
    example.sort(key=lambda r: int(r['source_side_idx']))
    example_fields = ['source_side_idx', 'possession_throw', 'PointStartTime', 'time_left',
                      'game_time_left', 'source_timestamp', 'sort_timestamp_imputed']
    reset_raw = raw['2026-06-14-CHI-PIT']['homeEvents'][51]
    discovery = json.loads((METADATA / 'metric-discovery.json').read_text())
    inventory = defaultdict(list)
    for c in discovery['columns']:
        inventory[c['table_name']].append(c['column_name'])
    result = {
        'status': 'Availability audit only; no timing-outcome comparison or player ranking performed.',
        'scope': {'season': 2026, 'competition': 'final regular-season games', 'export_rows': len(throws),
                  'games_with_export_rows': len({r['GameID'] for r in throws}),
                  'raw_games': len(raw), 'missing_game': '2026-07-18-PIT-CHI'},
        'sources': {'export_manifest': str(SOURCE / 'manifest.json'), 'raw_receipt': str(RAW / 'source_receipt.json'),
                    'metric_schema_receipt': str(METADATA / 'metric-discovery.json'),
                    'note': 'Preserved exports, raw captures, and saved live metadata; no new live database query.'},
        'field_coverage': coverage,
        'sort_timestamp_imputed': dict(Counter(r['sort_timestamp_imputed'] for r in throws)),
        'raw_attempt_fields': {field: sum(raw_field_counts[str(t)][field] for t in ATTEMPTS)
                               for field in ['events', 'time', 'timestamp']},
        'clock_spacing': dict(clock_counts),
        'pointstarttime_changes_within_point_side': sum(len({r['PointStartTime'] for r in g}) > 1 for g in points.values()),
        'pointstarttime_changes_within_possession_group': sum(len({r['PointStartTime'] for r in g}) > 1 for g in possessions.values()),
        'clock_example': {
            'game': '2026-06-14-CHI-PIT', 'side': 'home', 'quarter': 1, 'point': 3,
            'rows': [{k: r[k] for k in example_fields} for r in example],
            'point_start_source_time': 232, 'next_point_start_source_time': 284,
            'inference': '52 clock seconds divided among 8 throws gives exactly 6.5 seconds per stored step; raw timestamp gaps are unequal. Strong evidence of interpolation, not a verified production formula.'},
        'pointstarttime_reset_example': {
            'game': '2026-06-14-CHI-PIT', 'side': 'home', 'quarter': 1, 'point': 4,
            'raw_index': 51, 'event_type': reset_raw['type'], 'source_time': reset_raw['time'],
            'stored_before': 436, 'stored_after': 381,
            'interpretation': 'Stored PointStartTime changes at a timeout within the same point and possession; it is not always the original point start.'},
        'export_ordinal_checks': dict(ordinal_counts),
        'nonsequential_export_groups': nonsequential,
        'independent_raw_sequence_checks': dict(source_check),
        'ordinal_mismatch_examples': mismatch_examples,
        'huck_stage_support': dict(huck_check),
        'huck_point_context_support': dict(point_context_support),
        'huck_ordinal_counts_matching_raw_source': dict(sorted(Counter(int(float(r['possession_throw'])) for r in eligible).items())),
        'aggregate_table_columns': dict(inventory),
        'decisions': [
            'Use source-validated throw ordinal to measure progression within a possession.',
            'Do not treat stored time_left or game_time_left as measured per-throw clocks.',
            'Do not subtract PointStartTime blindly; it can reset within a point.',
            'Raw timestamps are not verified active playing seconds; recording delay, clock stoppages, and missingness remain unresolved.',
            'Separate receiving-pull possessions from possessions beginning after an opponent turnover.',
            'Track whether the team started the point receiving or pulling, its attacking-possession number, and only turnovers that preceded the throw.',
            'Include receiving-team possessions after regaining the disc whether the point eventually ends in a hold or a break.',
            'Point-start role is not a claim that the original seven players remain on the field after timeouts or injuries.',
            'Huck choice rate requires all eligible player throws at that stage as the denominator.',
            'Keep point age distinct from possession age; verified seconds can be added later.',
        ],
        'unresolved': [
            'Exact production derivation of time_left and PointStartTime.',
            'Whether raw timestamp records action time or stat-entry time, and how stopped-clock intervals should be removed.',
            'Resolve/exclude mismatched source ordinals before outcome analysis; stage-support counts are provisional.',
            'No observed receiver openness, defensive force, fatigue, or impatience.',
        ],
    }
    (ROOT / 'timing_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['scope', 'field_coverage', 'raw_attempt_fields', 'clock_spacing',
                                           'export_ordinal_checks', 'independent_raw_sequence_checks', 'huck_stage_support']}, indent=2))


if __name__ == '__main__':
    main()
