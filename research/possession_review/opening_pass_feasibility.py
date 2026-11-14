"""Inventory opening passes for classification development; never assign labels.

Geometry groups organize review. They are not inferred centering decisions.
Saved human labels, film-visibility limits, and coordinate holds stay separate.
"""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
COHORT = ROOT.parent / 'oline_possessions'
RAW = ROOT.parent / 'dead_disc_study/raw_events'
EXPORT = REPO / 'data/database-exports/2026-10-12'
PERIOD_ENDS = {28, 29, 30, 31, 32, 33}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def number(value):
    return None if value in ('', None) else float(value)


def main():
    inputs = {name: path for name, path in [
        ('possessions', COHORT / 'possessions.csv'), ('throws', COHORT / 'throws.csv'),
        ('cohort_audit', COHORT / 'cohort_audit.json'),
        ('review_audit', ROOT / 'review_batch_2026-11-12.json'),
        ('film_library', ROOT / 'film_library.json'),
        ('lineup_audit', COHORT / 'original_line_scoring.json'),
        ('raw_receipt', RAW / 'source_receipt.json'),
        ('export_manifest', EXPORT / 'manifest.json'),
        ('saved_timing_audit', ROOT.parent / 'huck_timing_study/timing_audit.json'),
        ('calculation', Path(__file__))]}
    manifest = json.loads(inputs['export_manifest'].read_text())
    assert sha(EXPORT / 'throws.csv') == manifest['tables']['throws']['sha256']
    audit = json.loads(inputs['review_audit'].read_text())
    library = json.loads(inputs['film_library'].read_text())
    assert sha(inputs['possessions']) == library['sourceInputs']['possessionsSha256']
    assert sha(inputs['throws']) == library['sourceInputs']['throwsSha256']
    decisions = {r['possessionId']: r for r in audit['allReviewedRows'] if r['ownPossession'] == 1}
    lineup = {r['possession_id']: r for r in json.loads(inputs['lineup_audit'].read_text())['rows']}
    openings = [p for p in read_csv(inputs['possessions']) if int(p['own_possession']) == 1]
    assert len({p['possession_id'] for p in openings}) == len(openings)
    throws = defaultdict(list)
    for t in read_csv(inputs['throws']):
        if int(t['own_possession']) == 1:
            throws[t['possession_id']].append(t)
    for ts in throws.values():
        ts.sort(key=lambda t: int(t['ordinal']))
    first_keys = {(p['GameID'], p['possession_id'].split('|')[1], throws[p['possession_id']][0]['source_side_idx'])
                  for p in openings if throws[p['possession_id']]}
    exported_first = {}
    with (EXPORT / 'throws.csv').open(newline='') as handle:
        for t in csv.DictReader(handle):
            key = (t['GameID'], t['source_side'], t['source_side_idx'])
            if key in first_keys:
                assert key not in exported_first
                exported_first[key] = t
    assert len(exported_first) == len(first_keys)
    receipts = json.loads(inputs['raw_receipt'].read_text())
    raw, peer_points = {}, {}
    for gid in sorted({p['GameID'] for p in openings}):
        path = RAW / (gid + '.json')
        assert sha(path) == receipts[gid]['sha256']
        raw[gid] = json.loads(path.read_text())['data']
        for side in ('home', 'away'):
            events = raw[gid][side + 'Events']
            quarter = 1
            for i, event in enumerate(events):
                if event['type'] == 1:
                    end = next((j for j in range(i+1, len(events)) if events[j]['type'] in {1, 2} | PERIOD_ENDS), len(events))
                    peer_points.setdefault((gid, side, quarter, event.get('time')), []).append((i, end))
                if event['type'] in PERIOD_ENDS:
                    quarter = event['type'] - 26
    rows = []
    timing = Counter()
    negative_examples = []
    for p in openings:
        pid, gid, side = p['possession_id'], p['GameID'], p['possession_id'].split('|')[1]
        events = raw[gid][side + 'Events']
        pi = int(p['point_id'].rsplit('|', 1)[1])
        assert events[pi]['type'] == 2
        opposite = 'away' if side == 'home' else 'home'
        peers = peer_points.get((gid, opposite, int(p['quarter']), events[pi].get('time')), [])
        pull_events = [] if len(peers) != 1 else [e for e in raw[gid][opposite+'Events'][peers[0][0]:peers[0][1]] if e['type'] in {7, 8}]
        pull = pull_events[0] if len(pull_events) == 1 else None
        reviewed = decisions.get(pid)
        checks = reviewed['reviewChecks'] if reviewed else []
        coordinate_hold = any(c.get('blocksFieldPositionMatch') for c in checks)
        # The earlier review also records a brick plus penalty location issue.
        coordinate_hold = coordinate_hold or bool(reviewed and reviewed['caseId'] == 'R052')
        label_hold = any(c.get('blocksAttackingCount') for c in checks)
        film_missing = any(c.get('visibilityStatus') == 'opening_not_shown' for c in checks)
        row = {'possession_id': pid, 'game_id': gid, 'team': p['team_name'],
               'quarter': int(p['quarter']), 'physical_throws': int(p['throws']),
               'review_case': reviewed['caseId'] if reviewed else '',
               'human_label': reviewed['review']['decision'] if reviewed else '',
               'human_context': reviewed['review']['context'] if reviewed else '',
               'coordinate_hold': coordinate_hold, 'label_alignment_hold': label_hold,
               'opening_missing_from_film': film_missing,
               'coordinate_development_label': bool(reviewed and not(coordinate_hold or label_hold or film_missing)),
               'pull_event_type': pull['type'] if pull else None,
               'pull_hangtime_ms': pull.get('pullMs') if pull else None,
               'pull_match': 'unique' if pull else 'unresolved',
               'pull_timestamp': pull.get('timestamp') if pull else None,
               'first_throw_timestamp': None, 'first_throw_has_game_clock': False,
               'timestamp_gap_throw1_to_throw2': None, 'timestamp_gap_pull_to_throw1': None,
               'first_attempt_original_line': None,
               'geometry_bucket': 'No physical throw', 'tx': None, 'ty': None, 'rx': None, 'ry': None,
               'mirrored_tx': None, 'mirrored_rx': None,
               'distance': None, 'forward_gain': None, 'inward_gain': None,
               'first_is_huck': None, 'first_attempt_event_type': None,
               'before_first_event_types': [],
               'review_url': 'https://shownspace.com/game-center/' + gid}
        ts = throws[pid]
        if ts:
            t = ts[0]
            idx = int(t['source_side_idx'])
            event = events[idx]
            x, y, rx, ry = [float(t[k]) for k in ('tx', 'ty', 'rx', 'ry')]
            raw_xy = [event['throwerX'], event['throwerY'], event.get('receiverX', event.get('turnoverX')), event.get('receiverY', event.get('turnoverY'))]
            assert all(math.isclose(a, b, rel_tol=0, abs_tol=1e-8) for a, b in zip([x, y, rx, ry], raw_xy))
            source = exported_first[(gid, side, t['source_side_idx'])]
            assert number(source['source_timestamp']) == number(event.get('timestamp'))
            issue = lineup[pid]['first_issue']
            sign = -1 if x < 0 else 1
            row.update(tx=x, ty=y, rx=rx, ry=ry, mirrored_tx=sign*x, mirrored_rx=sign*rx,
                       distance=math.hypot(rx-x, ry-y), forward_gain=ry-y, inward_gain=abs(x)-abs(rx),
                       first_is_huck=bool(int(t['huck'])), first_attempt_event_type=event['type'],
                       first_throw_timestamp=event.get('timestamp'), first_throw_has_game_clock='time' in event,
                       first_attempt_original_line=not issue or idx < issue['index'],
                       before_first_event_types=[e['type'] for e in events[pi+1:idx]])
            timing['first_throws'] += 1
            timing['first_throws_with_source_timestamp'] += event.get('timestamp') is not None
            timing['first_throws_with_game_clock'] += 'time' in event
            timing['first_throws_with_imputed_sort_time'] += source['sort_timestamp_imputed'] == 'true'
            if len(ts) > 1:
                second = events[int(ts[1]['source_side_idx'])]
                if event.get('timestamp') is not None and second.get('timestamp') is not None:
                    row['timestamp_gap_throw1_to_throw2'] = second['timestamp']-event['timestamp']
                    timing['first_two_throws_timestamp_pair'] += 1
                    timing['first_two_throws_nonpositive_gap'] += row['timestamp_gap_throw1_to_throw2'] <= 0
            if pull and pull.get('timestamp') is not None and event.get('timestamp') is not None:
                gap = event['timestamp']-pull['timestamp']
                row['timestamp_gap_pull_to_throw1'] = gap
                timing['matched_pull_and_first_timestamp_pairs'] += 1
                timing['first_throw_logged_before_opposing_pull'] += gap < 0
                if gap < 0 and len(negative_examples) < 5:
                    negative_examples.append({'possession_id': pid, 'pull_timestamp': pull['timestamp'],
                                              'first_throw_timestamp': event['timestamp'], 'gap_seconds': gap})
            # Mutually exclusive navigation bins, deliberately not classifier labels.
            if row['distance'] == 0:
                bucket = 'Repeated coordinates'
            elif row['first_is_huck']:
                bucket = 'First attempt is a huck'
            elif abs(x) <= 1 and abs(y-40) <= 1:
                bucket = 'Near brick coordinates'
            elif abs(x) >= 23:
                bucket = 'Sideline opening'
            elif row['distance'] <= 30 and row['inward_gain'] > 0:
                bucket = 'Shorter pass toward middle'
            elif row['distance'] <= 30:
                bucket = 'Shorter pass not toward middle'
            else:
                bucket = 'Other longer opening pass'
            row['geometry_bucket'] = bucket
        rows.append(row)
    reviewed_rows = [r for r in rows if r['human_label']]
    trusted = [r for r in reviewed_rows if r['coordinate_development_label']]
    groups = []
    for bucket, n in Counter(r['geometry_bucket'] for r in rows).items():
        rs = [r for r in rows if r['geometry_bucket'] == bucket]
        groups.append({'bucket': bucket, 'openings': n,
                       'saved_labels': dict(Counter(r['human_label'] for r in rs if r['human_label'])),
                       'coordinate_development_labels': dict(Counter(r['human_label'] for r in rs if r['coordinate_development_label']))})
    assert sum(g['openings'] for g in groups) == len(rows)
    assert len(reviewed_rows) == 38
    result = {
        'reviewedOn': '2026-11-13', 'status': 'Feasibility and review organization only; no automatic labels or metric changes.',
        'scope': {'opening_possessions': len(rows), 'physical_first_throws': timing['first_throws'],
                  'no_physical_throw': sum(r['physical_throws'] == 0 for r in rows),
                  'games': len(raw), 'teams': len({r['team'] for r in rows}),
                  'saved_opening_labels': len(reviewed_rows),
                  'saved_opening_label_counts': dict(Counter(r['human_label'] for r in reviewed_rows)),
                  'coordinate_development_labels': len(trusted),
                  'coordinate_development_label_counts': dict(Counter(r['human_label'] for r in trusted)),
                  'first_throws_before_original_line_cutoff': sum(r['first_attempt_original_line'] is True for r in rows)},
        'timing': dict(timing), 'timestamp_order_counterexamples': negative_examples,
        'geometry_groups': groups,
        'review_grouping_only': {
            'order': ['No physical throw', 'Repeated coordinates', 'First attempt is a huck',
                      'Near brick coordinates', 'Sideline opening', 'Shorter pass toward middle',
                      'Shorter pass not toward middle', 'Other longer opening pass'],
            'thresholds': {'near_brick_abs_x_at_most': 1, 'near_brick_y': 40, 'near_brick_y_tolerance': 1,
                           'sideline_abs_x_at_least': 23, 'shorter_pass_distance_at_most': 30},
            'meaning': 'Convenience bins for reviewing route shapes, not definitions of centering or validated prediction rules. Buckets are mutually exclusive in the listed priority order; review labels never follow from these counts.'},
        'reviewed_counterexamples': {
            'setup_not_moving_inward': [r['review_case'] for r in trusted if r['human_label']=='setup1' and r['inward_gain']<=0],
            'attack_moving_inward': [r['review_case'] for r in trusted if r['human_label']=='attack1' and r['inward_gain']>0],
            'held_from_coordinate_development': [{'case': r['review_case'], 'coordinate_hold': r['coordinate_hold'],
                'opening_missing_from_film': r['opening_missing_from_film'], 'label_alignment_hold': r['label_alignment_hold']}
                for r in reviewed_rows if not r['coordinate_development_label']]},
        'decisions': [
            'Use recorded field coordinates directly; no video-to-field coordinate extraction is needed for this first pilot.',
            'Mirror left/right only to group similar route shapes. Retain original coordinates and field side; this is not an assumption that defensive force is symmetric.',
            'Geometry buckets and pull records organize review, not confirmed centering versus attack labels. Near-brick coordinates do not establish a brick restart.',
            'Recorded event timestamps have unverified action-time meaning. Clock fields previously showed strong interpolation evidence; neither supports a fast-first-pass threshold yet.',
            'The relevant timing feature is pull caught/picked up to first release. First-to-second-pass spacing describes the next receiver and is not that interval.',
            'Do not train on later huck occurrence, possession length or scoring outcome to decide whether to subtract the opening pass.',
            'Existing reviewed openings were purposefully selected, mostly first-quarter, and some had visible suggestions. They are development examples, not accuracy or league prevalence estimates.',
            'Test a simple context-and-geometry rule or shallow classifier on untouched games and later quarters, with a random audit of routine predictions as well as ambiguous cases.',
            'Keep confirmed, suggested and unresolved labels separate. Do not remove one throw from unreviewed openings until the rule is validated.'
        ],
        'inputs': {name: {'path': str(path.relative_to(REPO)), 'sha256': sha(path)} for name, path in inputs.items()},
        'source_export_throws_sha256': manifest['tables']['throws']['sha256'],
        'rawGameHashes': {gid: receipts[gid]['sha256'] for gid in raw},
        'validation': {'uniqueOpeningIds': True, 'sourceHashChecksPassed': True, 'firstCoordinatesMatchRaw': True,
                       'sourceTimestampsMatchRaw': True, 'groupCountsReconcile': True, 'savedLabelsUnchanged': True},
        'rows': rows}
    (ROOT / 'opening_pass_feasibility.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['scope','timing','geometry_groups','reviewed_counterexamples','timestamp_order_counterexamples']}, indent=2))


if __name__ == '__main__':
    main()
