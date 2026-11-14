"""Recalculate scoring while following the original receiving-point seven.

Keep the earlier no-timeout-within-possession filter, then stop each original
line's sequence at its first recorded personnel change or contradictory player
record. Do not discard completed possessions because of a later substitution.
Source rows and previous results remain unchanged.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json

import numpy as np
import pandas as pd
import analyze

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RAW = ROOT.parent / 'dead_disc_study/raw_events'
STOPPAGES = {3, 5, 25}
ATTEMPTS = {18, 19, 20, 22, 23, 24}
PHYSICAL = ATTEMPTS - {24}
UNKNOWN = {'unknown', ''}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_line(line):
    return (isinstance(line, list) and len(line) == len(set(line)) == 7
            and all(isinstance(player, str) and player not in UNKNOWN for player in line))


def inspect_point(events, start, end):
    original = events[start].get('line')
    valid = valid_line(original)
    issues = []
    unknown_actors = []
    if not valid:
        issues.append({'index': start, 'kind': 'opening_line_unknown', 'type': events[start]['type']})
    else:
        original_set = set(original)
        for i in range(start + 1, end + 1):
            event = events[i]
            if event['type'] in STOPPAGES and 'line' not in event:
                issues.append({'index': i, 'kind': 'missing_line_update', 'type': event['type']})
            if 'line' in event:
                if not valid_line(event['line']):
                    issues.append({'index': i, 'kind': 'incomplete_line_update', 'type': event['type']})
                elif set(event['line']) != original_set:
                    issues.append({'index': i, 'kind': 'line_changed', 'type': event['type'],
                                   'players_replaced': len(set(event['line']) - original_set)})
            if event['type'] in ATTEMPTS:
                for key in ['thrower'] + (['receiver'] if event['type'] in {18, 19} else []):
                    player = event.get(key)
                    if player is None or player in UNKNOWN:
                        unknown_actors.append(i)
                    elif player not in original_set:
                        issues.append({'index': i, 'kind': 'player_not_in_opening_line',
                                       'type': event['type'], 'field': key, 'player': player})
    return {'original': original, 'issues': issues, 'unknown_actors': unknown_actors}


def main():
    paths = {'possessions': ROOT / 'possessions.csv', 'results': ROOT / 'results.json',
             'raw_receipt': RAW / 'source_receipt.json', 'analysis': ROOT / 'analyze.py',
             'calculation': Path(__file__)}
    base = json.loads(paths['results'].read_text())
    assert sha(paths['possessions']) == base['inputs']['possessions.csv']
    receipt = json.loads(paths['raw_receipt'].read_text())
    with paths['possessions'].open(newline='') as f:
        records = list(csv.DictReader(f))
    assert len({p['possession_id'] for p in records}) == len(records)
    raw = {}
    point_ends = {}
    for p in records:
        point_ends[p['point_id']] = max(point_ends.get(p['point_id'], 0), int(p['end_idx']))
    points = {}
    for point_id, end in point_ends.items():
        gid, side, index = point_id.split('|')
        if gid not in raw:
            path = RAW / (gid + '.json')
            assert sha(path) == receipt[gid]['sha256']
            raw[gid] = json.loads(path.read_text())['data']
        events = raw[gid][side + 'Events']
        assert events[int(index)]['type'] == 2
        points[point_id] = inspect_point(events, int(index), end)

    rows = []
    for p in records:
        state = points[p['point_id']]
        start, end = int(p['start_idx']), int(p['end_idx'])
        issues = [x for x in state['issues'] if x['index'] <= end]
        first_issue = issues[0] if issues else None
        old = p['has_timeout'] == 'False' and p['outcome'] in {'goal', 'turnover'}
        gid, side = p['point_id'].split('|')[:2]
        events = raw[gid][side + 'Events']
        assert events[end]['type'] == int(p['end_type'])
        assert int(p['goal']) == int(events[end]['type'] in {12, 19})
        physical = [i for i in range(start + 1, end + 1) if events[i]['type'] in PHYSICAL]
        assert len(physical) == int(p['throws'])
        change_events = [x for x in issues if x['kind'] == 'line_changed']
        rows.append({'possession_id': p['possession_id'], 'GameID': gid,
                     'team': p['team'], 'own_possession': int(p['own_possession']),
                     'stage': int(p['stage']), 'outcome': p['outcome'], 'goal': int(p['goal']),
                     'old_eligible': old, 'line_eligible': not issues,
                     'included': old and not issues,
                     'has_timeout': p['has_timeout'] == 'True',
                     'prior_timeout': p['prior_timeout'] == 'True',
                     'opening_seven': state['original'], 'first_issue': first_issue,
                     'first_line_change': change_events[0] if change_events else None,
                     'change_timing': ('before_possession' if first_issue['index'] <= start else 'during_possession') if first_issue else None,
                     'physical_throws_before_cutoff': sum(i < first_issue['index'] for i in physical) if first_issue else len(physical),
                     'unknown_actor_events': sorted(set(i for i in state['unknown_actors'] if start < i <= end))})

    p_all = pd.read_csv(paths['possessions'])
    by_id = {r['possession_id']: r for r in rows}
    p = p_all[p_all.possession_id.map(lambda pid: by_id[pid]['included'])].copy()
    line_all = p_all[p_all.possession_id.map(lambda pid: by_id[pid]['line_eligible'])].copy()
    no_timeout = line_all[~line_all.has_timeout].copy()
    analyze.RNG = np.random.default_rng(20261113)
    observed = analyze.observed(p, 'goal')
    observed['first_vs_all_subsequent'] = analyze.observed(p, 'goal', (0, 1), 'regained')
    print('Lineup audit and observed scoring complete.', flush=True)
    prepared = analyze.prepare(p, p_all.drop_duplicates('point_id').set_index('point_id'))
    adjusted = analyze.adjusted(prepared, 'goal')
    changes = analyze.team_changes(prepared, 'goal')
    teams = []
    for tid, group in p.groupby('team', sort=True):
        obs = analyze.observed(group, 'goal')
        obs['first_vs_all_subsequent'] = analyze.observed(group, 'goal', (0, 1), 'regained')
        exact = analyze.observed(group[group.own_possession.le(3)], 'goal', (1, 2, 3), 'own_possession')['groups']
        for g in obs['groups'] + exact:
            if g['games'] < 2:
                g['ci95'] = None
                g['ciReason'] = 'Fewer than two contributing games.'
            elif g['sum'] in {0, g['n']}:
                g['ci95'] = None
                g['ciReason'] = 'All observed outcomes are identical; the bootstrap cannot estimate outcome uncertainty.'
        exact[2]['name'] = 'Third'
        teams.append({'team': tid, 'team_name': group.team_name.iloc[0], 'observed': obs, 'exact': exact})
    bands = ['Own end zone: 0–20', 'Deep own half: 20–40', 'To midfield: 40–60',
             'Attacking half: 60–80', 'Near goal: 80–120']
    known = p[p.first_y.notna()].copy()
    known['start_band'] = pd.cut(known.first_y, [-.01, 20, 40, 60, 80, 120], labels=bands, right=True)
    scoring_by_start = [{'band': str(b), 'stage': int(s), 'n': len(g),
                         'goals': int(g.goal.sum()), 'rate': float(g.goal.mean())}
                        for (b, s), g in known.groupby(['start_band', 'stage'], observed=True)]
    excluded = [r for r in rows if r['old_eligible'] and not r['included']]
    removed = []
    for stage in (1, 2, 3):
        q = [r for r in excluded if r['stage'] == stage]
        removed.append({'stage': stage, 'n': len(q), 'goals': sum(r['goal'] for r in q),
                        'line_change_n': sum(r['first_line_change'] is not None for r in q),
                        'reasons': dict(Counter(r['first_issue']['kind'] for r in q))})

    # Independent raw-event pass: no retained possession can follow an update
    # to a different seven, an incomplete update, or a contradictory actor.
    record_by_id = {p['possession_id']: p for p in records}
    for row in [r for r in rows if r['included']]:
        source = record_by_id[row['possession_id']]
        gid, side, pi = source['point_id'].split('|')
        events = raw[gid][side + 'Events']
        original = events[int(pi)]['line']
        assert len(original) == len(set(original)) == 7 and 'unknown' not in original
        for event in events[int(pi)+1:int(source['end_idx'])+1]:
            if event['type'] in STOPPAGES:
                assert len(event['line']) == 7
            if 'line' in event:
                assert sorted(event['line']) == sorted(original)
            if event['type'] in ATTEMPTS:
                for k in ['thrower'] + (['receiver'] if event['type'] in {18, 19} else []):
                    assert not event.get(k) or event[k] == 'unknown' or event[k] in original
    for outcome in ('goal', 'turnover'):
        assert sum(r['outcome'] == outcome for r in rows if r['included']) == int(p.outcome.eq(outcome).sum())
    for group in observed['groups']:
        subset = [r for r in rows if r['included'] and r['stage'] == group['stage']]
        assert len(subset) == group['n'] and sum(r['goal'] for r in subset) == group['sum']
        prior = base['league']['scoring']['groups'][group['stage']-1]
        removal = removed[group['stage']-1]
        assert prior['n'] - removal['n'] == group['n']
        assert prior['sum'] - removal['goals'] == group['sum']
    for team in teams:
        for g in team['exact']:
            q = [r for r in rows if r['included'] and r['team'] == team['team'] and r['own_possession'] == g['stage']]
            assert len(q) == g['n'] and sum(r['goal'] for r in q) == g['sum']
    for pid in ['2026-04-24-ATL-HTX|home|26|2', '2026-05-09-PHI-CAR|home|22|2']:
        assert not by_id[pid]['included']
        opening_id = pid.rsplit('|', 1)[0] + '|1'
        assert by_id[opening_id]['included'], 'Keep the original opening possession before replacement.'
    assert all(r['own_possession'] == int(record_by_id[r['possession_id']]['own_possession']) for r in rows)
    result = {
        'updatedOn': '2026-11-13',
        'definitions': {
            'unit': 'Completed offensive possessions by the original seven receiving-point players.',
            'cutoff': 'Stop at the first recorded personnel change, incomplete lineup update, or named passer/catcher outside the opening seven. Keep completed possessions before that event; never resume or renumber the sequence.',
            'partial': 'A possession crossing the cutoff is omitted from the completed-possession scoring denominator. Earlier physical throws remain preserved in the audit and original source, without assigning the replacement line outcome to them.',
            'timeout': 'The earlier exclusion of possessions containing timeout events 3 or 5 remains in the main comparison. A prior timeout alone is not exclusion: later possessions count only if records still support the same seven. This is tested separately from timeout caller.',
            'unknown': 'Incomplete opening lineups and contradictory named players are excluded. Unknown actor IDs alone are flagged rather than treated as substitutions when the lineup records remain complete.',
            'outcome': 'Goal / (goal + turnover). Period endings are excluded and retained as a sensitivity calculation; no removal of near-goal starts.',
            'selection': 'All eligible opening possessions are the baseline, including points with a later substitution. Later rates are conditional on reaching that possession with the original seven.',
            'limit': 'Recorded personnel continuity is not independent film verification of every substitution. Unrecorded changes or incorrect source lineups can remain undetected.',
            'inference': 'Exploratory update. Observed ranges resample whole games 10000 times, seed 20261113; adjusted ranges use the prior context formula with game-clustered covariance. Updated scoring contrasts are not covered by the old multi-metric Holm results; team_changes includes its own 22-team Holm adjustment.'
        },
        'scope': {'source_possessions': len(rows), 'old_resolved': sum(r['old_eligible'] for r in rows),
                  'resolved': len(p), 'games': int(p.GameID.nunique()), 'teams': int(p.team.nunique()),
                  'removed_from_old': len(excluded), 'removed_by_stage': removed,
                  'period_end': int(no_timeout.outcome.eq('period_end').sum()),
                  'model_n': len(prepared), 'model_missing_context': len(p)-len(prepared),
                  'unknown_actor_possessions_retained': sum(bool(r['unknown_actor_events']) for r in rows if r['included'])},
        'observed': observed, 'adjusted': adjusted, 'team_changes': changes, 'teams': teams,
        'scoring_by_start': scoring_by_start,
        'sensitivity': {'period_end_as_no_goal': analyze.observed(no_timeout, 'goal'),
                        'include_same_line_timeout_possessions': analyze.observed(line_all[line_all.outcome.isin(['goal', 'turnover'])], 'goal'),
                        'no_prior_timeouts': analyze.observed(p[~p.prior_timeout], 'goal')},
        'rows': rows,
        'inputs': {name: {'path': str(path.relative_to(REPO)), 'sha256': sha(path)} for name, path in paths.items()},
        'rawGameHashes': {gid: receipt[gid]['sha256'] for gid in raw},
        'environment': {'numpy': np.__version__, 'pandas': pd.__version__,
                        'scipy': analyze.scipy.__version__, 'statsmodels': analyze.statsmodels.__version__,
                        'patsy': analyze.patsy.__version__, 'bootstrap_seed': 20261113},
        'validation': {'passed': True, 'everyIncludedPossessionCheckedAgainstRawLineups': True,
                       'oldCountsMinusExclusionsReconcile': True, 'exactTeamGroupsChecked': len(teams)*3,
                       'originalPossessionNumbersPreserved': True, 'reviewedReplacementExamplesExcluded': True,
                       'completedOpeningsBeforeReplacementsRetained': True}
    }
    analyze.dump('original_line_scoring.json', result)
    print(json.dumps(analyze.clean({'scope': result['scope'], 'observed': observed['groups'],
                                  'adjusted': adjusted['groups'], 'differences': adjusted['differences']}), indent=2))


if __name__ == '__main__':
    main()
