"""Bound the effect of unresolved opening labels without predicting those labels.

One fixed cohort: complete goal/turnover possessions by the original seven,
excluding possessions containing timeouts. Retain original starting coordinates.
These are deterministic label-sensitivity ranges, not confidence intervals.
"""
from pathlib import Path
import csv
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVIEW = HERE.parent / 'possession_review'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(n, d):
    return n / d if d else None


def summarize(rows):
    n = len(rows)
    attempts = sum(r['attempts'] for r in rows)
    hucks = sum(r['hucks'] for r in rows)
    known = sum(r['deduct_known'] for r in rows)
    known_hucks = sum(r['deduct_known'] and r['first_huck'] for r in rows)
    unknown = sum(r['deduct_unknown'] for r in rows)
    unknown_hucks = sum(r['deduct_unknown'] and r['first_huck'] for r in rows)
    unknown_nonhucks = unknown - unknown_hucks
    assert 0 <= known + unknown <= n and known + unknown <= attempts
    base_attempts, base_hucks = attempts - known, hucks - known_hucks
    # Removing a huck lowers its share; removing a non-huck raises it.
    # We allow both possibilities for unresolved completed first throws rather
    # than inventing a maximum setup distance. No failed attempts are removed.
    return {'possessions': n, 'games': len({r['game'] for r in rows}),
            'attempts': attempts, 'hucks': hucks,
            'goals': sum(r['outcome'] == 'goal' for r in rows),
            'confirmed_deductions': known, 'unknown_possible_deductions': unknown,
            'unknown_first_hucks': unknown_hucks,
            'mean_all_throws': rate(attempts, n),
            'mean_confirmed_only': rate(base_attempts, n),
            'mean_label_range': [rate(base_attempts - unknown, n), rate(base_attempts, n)],
            'huck_attempt_share_all': rate(hucks, attempts),
            'huck_attempt_share_confirmed_only': rate(base_hucks, base_attempts),
            'huck_attempt_share_label_range': [rate(base_hucks - unknown_hucks, base_attempts - unknown_hucks),
                                               rate(base_hucks, base_attempts - unknown_nonhucks)]}


def comparisons(rows):
    groups = []
    for stage in (1, 2, 3):
        chosen = [r for r in rows if r['stage'] == stage]
        groups.append({'stage': stage, 'all': summarize(chosen),
                       'goal': summarize([r for r in chosen if r['outcome'] == 'goal']),
                       'turnover': summarize([r for r in chosen if r['outcome'] == 'turnover'])})
    first, second = groups[0]['all'], groups[1]['all']
    first_mean, second_mean = first['mean_label_range'], second['mean_all_throws']
    first_hap, second_hap = first['huck_attempt_share_label_range'], second['huck_attempt_share_all']
    return {'groups': groups, 'first_vs_second': {
        'mean_difference_range_second_minus_first':
            [second_mean - first_mean[1], second_mean - first_mean[0]] if second_mean is not None and first_mean[0] is not None else None,
        'huck_share_difference_range_second_minus_first':
            [second_hap - first_hap[1], second_hap - first_hap[0]] if second_hap is not None and first_hap[0] is not None and first_hap[1] is not None else None,
        'fewer_second_possession_throws_for_every_label_assignment':
            second_mean < first_mean[0] if second_mean is not None and first_mean[0] is not None else None,
        'higher_second_possession_huck_share_for_every_label_assignment':
            second_hap > first_hap[1] if second_hap is not None and first_hap[1] is not None else None,
    }}


def main():
    paths = {'possessions': HERE / 'possessions.csv', 'throws': HERE / 'throws.csv',
             'lineup_audit': HERE / 'original_line_scoring.json',
             'opening_labels': REVIEW / 'current_opening_label_inventory.json',
             'source_inventory': REVIEW / 'opening_pass_feasibility.json'}
    inputs = {k: {'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for k, p in paths.items()}
    audit = json.loads(paths['lineup_audit'].read_text())
    for source in audit['inputs'].values():
        assert sha(ROOT / source['path']) == source['sha256']
    source_inventory = json.loads(paths['source_inventory'].read_text())
    for name in ('possessions', 'throws'):
        assert inputs[name]['sha256'] == source_inventory['inputs'][name]['sha256']
    for game, digest in audit['rawGameHashes'].items():
        assert sha(HERE.parent / 'dead_disc_study/raw_events' / (game + '.json')) == digest
    labels = {r['possession_id']: r for r in json.loads(paths['opening_labels'].read_text())['rows']}
    eligibility = {r['possession_id']: r for r in audit['rows']}
    throws = {}
    with paths['throws'].open() as handle:
        for t in csv.DictReader(handle):
            throws.setdefault(t['possession_id'], []).append(t)
    rows = []
    with paths['possessions'].open() as handle:
        for p in csv.DictReader(handle):
            pid = p['possession_id']
            if not eligibility[pid]['included']:
                continue
            assert p['outcome'] in ('goal', 'turnover') and not eligibility[pid]['has_timeout']
            physical = sorted(throws.get(pid, []), key=lambda r: int(r['ordinal']))
            assert len(physical) == int(p['throws']) == eligibility[pid]['physical_throws_before_cutoff']
            hucks = sum(int(t['huck']) for t in physical)
            assert hucks == int(p['hucks'])
            own = int(p['own_possession'])
            first = physical[0] if physical else None
            completed = bool(first and int(first['source_event_type']) in (18, 19))
            label = labels.get(pid, {}).get('effective_label') if own == 1 else None
            known = own == 1 and label == 'setup1'
            possible = own == 1 and completed and label is None
            assert not known or completed
            first_y = float(p['first_y']) if p['first_y'] else None
            rows.append({'possession_id': pid, 'game': p['GameID'], 'team': p['team'],
                         'team_name': p['team_name'], 'own_possession': own, 'stage': min(own, 3),
                         'outcome': p['outcome'], 'first_y': first_y, 'attempts': len(physical),
                         'hucks': hucks, 'first_huck': bool(first and int(first['huck'])),
                         'deduct_known': known, 'deduct_unknown': possible})
    scopes = {}
    for key in ('long_field', 'all_starts'):
        sample = [r for r in rows if r['first_y'] is not None and r['first_y'] <= 40] if key == 'long_field' else rows
        teams = []
        for team in sorted({r['team'] for r in sample}):
            subset = [r for r in sample if r['team'] == team]
            teams.append({'team': team, 'team_name': subset[0]['team_name'], **comparisons(subset)})
        scopes[key] = {'league': comparisons(sample), 'teams': teams}
        for group in scopes[key]['league']['groups']:
            assert sum(t['groups'][group['stage'] - 1]['all']['attempts'] for t in teams) == group['all']['attempts']
            assert sum(t['groups'][group['stage'] - 1]['all']['possessions'] for t in teams) == group['all']['possessions']
        assert all(g['all']['confirmed_deductions'] == g['all']['unknown_possible_deductions'] == 0
                   for g in scopes[key]['league']['groups'] if g['stage'] > 1)
    result = {
        'updatedOn': '2026-11-13', 'id': 'opening-centering-label-sensitivity-20261113',
        'question': 'Could unresolved centering labels alone reverse the observed first-versus-second possession differences?',
        'definitionVersion': 'completed-centering-transfer-20261113',
        'cohort': 'Same complete goal/turnover possessions for both metrics; original seven verified by the existing audit; exclude possessions containing a timeout and period-ending possessions. This is narrower than the published all-attempt HAP cohort, which includes retained pre-substitution and period-ending throws.',
        'longField': 'Original first throwing location first_y <= 40: at least 60 yards from the attacking goal line. No re-anchoring after centering.',
        'method': 'For each unresolved completed opening first throw, allow either no deduction or one deduction. Confirmed centering gets one deduction; known no-centering and failed first attempts get none. Keep every possession and every goal/turnover. Later possessions get no deduction.',
        'rangeMeaning': 'Endpoints are possible results under unresolved labels. These are not 95% confidence intervals, predictions, or estimated centering prevalence.',
        'huckRange': 'To minimize huck share, remove only unresolved first throws that are hucks; to maximize it, remove only unresolved first throws that are not hucks. This deliberately broad bound does not impose an unapproved maximum setup distance.',
        'limits': [
            'Observed comparisons only: starting positions still vary inside the broad long-field group, and teams/points reaching a second possession are selected.',
            'Robustness to centering labels is not statistical significance and does not establish fatigue, impatience or a causal turnover effect.',
            'This check does not settle when within the attacking throw sequence a huck occurs.',
        ],
        'sourceFreshness': 'Preserved DBeaver export and captured UFA events; no live database refresh.',
        'scopes': scopes, 'inputs': inputs,
        'validation': {'sameCohortForBothMetrics': True, 'teamCountsReconcile': True,
                       'noLaterPossessionDeductions': True, 'sourceHashesVerified': True,
                       'sourceOutcomesAndPhysicalThrowsPreserved': True, 'noModelPredictedLabels': True},
    }
    (HERE / 'centering_sensitivity_bounds.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v['league'] for k, v in scopes.items()}, indent=2))


if __name__ == '__main__':
    main()
