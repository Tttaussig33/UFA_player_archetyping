"""Paired physical/attacking counts for human-reviewed possessions only.

This does not classify unreviewed openings or refit the league analysis.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REVIEW = ROOT.parent / 'possession_review'
RAW = ROOT.parent / 'dead_disc_study/raw_events'
PHYSICAL = {18, 19, 20, 22, 23}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inputs = {
        'review_audit': REVIEW / 'review_batch_2026-11-12.json',
        'film_library': REVIEW / 'film_library.json',
        'possessions': ROOT / 'possessions.csv',
        'throws': ROOT / 'throws.csv',
        'raw_receipt': RAW / 'source_receipt.json',
    }
    audit = json.loads(inputs['review_audit'].read_text())
    library = json.loads(inputs['film_library'].read_text())
    cases = {c['possessionId']: c for c in library['cases']}
    with inputs['possessions'].open(newline='') as f:
        possession_rows = list(csv.DictReader(f))
    possessions = {p['possession_id']: p for p in possession_rows}
    assert len(possessions) == len(possession_rows)
    with inputs['throws'].open(newline='') as f:
        throw_rows = list(csv.DictReader(f))
    throws = {}
    for throw in throw_rows:
        throws.setdefault(throw['possession_id'], []).append(throw)
    receipts = json.loads(inputs['raw_receipt'].read_text())
    raw = {}
    rows = []
    # These specific reviewed examples were flagged as end-of-quarter situations.
    # No general point-clock cutoff is inferred or applied to the league.
    known_period_end_examples = {'R033', 'R060'}
    for reviewed in audit['allReviewedRows']:
        pid = reviewed['possessionId']
        p, case = possessions[pid], cases[pid]
        gid, side = pid.split('|')[:2]
        if gid not in raw:
            path = RAW / (gid + '.json')
            assert sha(path) == receipts[gid]['sha256']
            raw[gid] = json.loads(path.read_text())['data']
        events = raw[gid][side + 'Events']
        point_start = int(p['point_id'].rsplit('|', 1)[1])
        start, end = int(p['start_idx']), int(p['end_idx'])
        original_line = events[point_start].get('line', [])
        valid_line = len(original_line) == 7 and len(set(original_line)) == 7
        changes = [i for i in range(point_start + 1, end + 1)
                   if 'line' in events[i] and set(events[i]['line']) != set(original_line)]
        raw_indices = [i for i in range(start + 1, end + 1) if events[i]['type'] in PHYSICAL]
        recorded = sorted(throws.get(pid, []), key=lambda t: int(t['ordinal']))
        assert [int(t['source_side_idx']) for t in recorded] == raw_indices
        assert [t['sourceIndex'] for t in case['throws']] == raw_indices
        assert len(raw_indices) == int(p['throws']) == reviewed['originalThrows']
        assert [t['n'] for t in case['throws']] == list(range(1, len(raw_indices) + 1))
        assert [bool(int(t['huck'])) for t in recorded] == [t['huck'] for t in case['throws']]
        decision = reviewed['review']['decision']
        held = any(c.get('blocksAttackingCount') for c in reviewed['reviewChecks'])
        remove = 1 if decision == 'setup1' and not held else 0 if decision == 'attack1' and not held else None
        if remove:
            assert reviewed['ownPossession'] == 1
            assert case['throws'] and not case['throws'][0]['huck']
        adjusted = len(raw_indices) - remove if remove is not None else None
        assert adjusted == reviewed['attackingThrows']
        reasons = []
        if remove is None:
            reasons.append('Unresolved pass label or clip-to-possession match')
        if not valid_line:
            reasons.append('Original seven players not established')
        if changes:
            reasons.append('Original lineup changed before this possession ended')
        if reviewed['caseId'] in known_period_end_examples:
            reasons.append('Reviewed end-of-quarter example')
        if p['outcome'] not in {'goal', 'turnover'}:
            reasons.append('Possession did not end with a goal or turnover')
        huck_positions = [int(t['ordinal']) for t in recorded if int(t['huck'])]
        row = {
            'caseId': reviewed['caseId'], 'possessionId': pid, 'gameId': gid,
            'team': reviewed['team'], 'ownPossession': reviewed['ownPossession'],
            'outcome': p['outcome'], 'decision': decision,
            'physicalThrows': len(raw_indices), 'centeringPassesRemoved': remove,
            'attackingThrows': adjusted, 'physicalHuckPositions': huck_positions,
            'attackingHuckPositions': [n - remove for n in huck_positions] if remove is not None else None,
            'originalStartXY': [float(p['first_x']), float(p['first_y'])],
            'startingLocationBasis': 'First recorded throw; unchanged when a centering pass is removed. Exact catch/pickup coordinates are not established by this proxy.',
            'goal': int(p['goal']), 'pointHold': int(p['point_hold']),
            'lineChangeIndices': changes,
            'physicalThrowsBeforeLineChange': sum(i < changes[0] for i in raw_indices) if changes else len(raw_indices),
            'timeoutBefore': p['prior_timeout'] == 'True', 'timeoutDuring': p['has_timeout'] == 'True',
            'included': not reasons, 'exclusionReasons': reasons,
            'fieldPositionMatchHeld': any(c.get('blocksFieldPositionMatch') for c in reviewed['reviewChecks']),
        }
        assert row['originalStartXY'] == reviewed['firstThrowXY'][:2]
        # Directly slice the preserved physical sequence as an independent count check.
        if remove is not None:
            assert adjusted == len(case['throws'][remove:])
        rows.append(row)
    assert len({r['possessionId'] for r in rows}) == len(rows) == len(audit['allReviewedRows'])
    included = [r for r in rows if r['included']]
    groups = {}
    for outcome in ('goal', 'turnover'):
        groups[outcome] = []
        for stage in (1, 2, 3):
            members = [r for r in included if r['outcome'] == outcome and min(r['ownPossession'], 3) == stage]
            if not members:
                continue
            raw_total = sum(r['physicalThrows'] for r in members)
            attack_total = sum(r['attackingThrows'] for r in members)
            removed = sum(r['centeringPassesRemoved'] for r in members)
            assert raw_total - attack_total == removed
            if stage > 1:
                assert removed == 0
            groups[outcome].append({
                'stage': stage, 'n': len(members), 'games': len({r['gameId'] for r in members}),
                'physicalTotal': raw_total, 'attackingTotal': attack_total,
                'centeringPassesRemoved': removed, 'physicalMean': raw_total / len(members),
                'attackingMean': attack_total / len(members),
                'caseIds': [r['caseId'] for r in members],
            })
    result = {
        'updatedOn': '2026-11-12', 'title': 'Throw counts with and without confirmed centering passes',
        'scope': {'reviewed': len(rows), 'included': len(included), 'excluded': len(rows) - len(included),
                  'games': len({r['gameId'] for r in included}),
                  'first': sum(r['ownPossession'] == 1 for r in included),
                  'second': sum(r['ownPossession'] == 2 for r in included),
                  'thirdOrLater': sum(r['ownPossession'] >= 3 for r in included)},
        'definitions': {
            'physical': 'Every physical pass attempt, including centering and incomplete throws.',
            'attacking': 'Subtract one human-confirmed opening centering/setup pass; retain every pass in a direct opening attack or a possession after a turnover.',
            'index': 'For a confirmed setup sequence, subtract one from each following physical throw number, including huck positions.',
            'fieldPosition': 'Keep the original possession-start location; do not shift eligibility or matching to the receiving end of a centering pass.',
            'sourceLocationLimit': 'Current x/y values are the first recorded throwing location, not independently verified exact pull-catch or pickup coordinates.',
            'setupFailures': 'Keep the physical attempt and turnover. A possession ending on a failed setup can have zero attacking throws.',
            'cohort': 'Same completed film-reviewed original-line possessions in both counts, separated into goals and turnovers. Stop at the first recorded lineup change, retain original possession numbers, and omit the two individually flagged end-of-quarter examples.',
            'scopeLimit': 'A counting demonstration on deliberately selected reviews. Starts are not field-matched. These means are not league estimates or evidence of a team tendency. No inferential intervals or p-values are estimated.',
            'uncertain': 'Do not automatically subtract from unreviewed or unresolved starts.',
        },
        'groups': groups, 'rows': rows,
        'exclusions': dict(Counter(reason for r in rows for reason in r['exclusionReasons'])),
        'primaryExclusions': [{'reason': reason, 'n': n} for reason, n in Counter(
            r['exclusionReasons'][0] for r in rows if r['exclusionReasons']).items()],
        'inputs': {name: {'path': str(path.relative_to(REPO)), 'sha256': sha(path)} for name, path in inputs.items()},
        'rawGameHashes': {gid: receipts[gid]['sha256'] for gid in raw},
        'validation': {'uniqueReviewedPossessions': True, 'allThrowCountsMatchRawEvents': True,
                       'huckFlagsMatchPreservedThrows': True, 'sameDenominatorsForBothViews': True,
                       'originalStartCoordinatesUnchanged': True, 'noUnreviewedLabelsInferred': True,
                       'outcomesAndPhysicalRecordsUnchanged': True},
    }
    (ROOT / 'reviewed_centering_counts.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'scope': result['scope'], 'groups': groups, 'exclusions': result['exclusions']}, indent=2))


if __name__ == '__main__':
    main()
