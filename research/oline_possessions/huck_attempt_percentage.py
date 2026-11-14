"""Team huck attempts / physical throw attempts, by receiving-team possession.

Reuse the audited original-seven cutoff, retaining actions before a substitution
even when the replacement line finishes the possession. This is a throw-level
rate, so a possession need not end in a goal or turnover to contribute attempts.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SEED = 20261113
DRAWS = 10000
RNG = np.random.default_rng(SEED)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def interval(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return np.quantile(values, [.025, .975]).tolist() if len(values) else None


def summarize(rows, category='stage', categories=(1, 2, 3), outcome='huck'):
    games = sorted(rows.GameID.unique())
    totals = np.zeros((len(games), len(categories)), dtype=int)
    hucks = np.zeros_like(totals)
    gi = pd.Categorical(rows.GameID, categories=games).codes
    ci = pd.Categorical(rows[category], categories=categories).codes
    assert (ci >= 0).all()
    np.add.at(totals, (gi, ci), 1)
    np.add.at(hucks, (gi, ci), rows[outcome].to_numpy(int))
    weights = RNG.multinomial(len(games), np.full(len(games), 1 / len(games)), size=DRAWS)
    with np.errstate(divide='ignore', invalid='ignore'):
        simulated = (weights @ hucks) / (weights @ totals)
        means = hucks.sum(0) / totals.sum(0)
    groups = []
    for i, k in enumerate(categories):
        subset = rows[rows[category].eq(k)]
        n, y = int(totals[:, i].sum()), int(hucks[:, i].sum())
        g = {'stage': k, 'n': n, 'sum': y, 'estimate': means[i],
             'games': int(subset.GameID.nunique()),
             'possessions': int(subset.possession_id.nunique()),
             'ci95': interval(simulated[:, i])}
        if g['games'] < 2 or y in {0, n}:
            g['ci95'] = None
        groups.append(g)
        assert n == len(subset) and y == int(subset[outcome].sum())
    differences = [{'from': categories[0], 'to': k,
                    'difference': means[i] - means[0],
                    'ci95': interval(simulated[:, i] - simulated[:, 0])}
                   for i, k in enumerate(categories) if i]
    return clean({'groups': groups, 'games': len(games), 'differences': differences})


def descriptive(rows, outcome='huck'):
    return [{'stage': stage, 'sum': int(g[outcome].sum()), 'n': len(g),
             'estimate': float(g[outcome].mean())}
            for stage, g in rows.groupby('stage', sort=True)]


def main():
    inputs = {name: ROOT / name for name in ['throws.csv', 'possessions.csv',
              'original_line_scoring.json', 'cohort_audit.json']}
    inputs['calculation'] = Path(__file__)
    audit = json.loads(inputs['original_line_scoring.json'].read_text())
    assert audit['validation']['passed']
    for source in audit['inputs'].values():
        assert sha(REPO / source['path']) == source['sha256']
    cohort = json.loads(inputs['cohort_audit.json'].read_text())
    assert sha(inputs['throws.csv']) == json.loads((ROOT / 'results.json').read_text())['inputs']['throws.csv']
    raw_dir = ROOT.parent / 'dead_disc_study/raw_events'
    for game, digest in audit['rawGameHashes'].items():
        assert sha(raw_dir / (game + '.json')) == digest
    throws = pd.read_csv(inputs['throws.csv'])
    possessions = pd.read_csv(inputs['possessions.csv']).set_index('possession_id')
    by_id = {r['possession_id']: r for r in audit['rows']}
    assert not throws.duplicated(['GameID', 'source_side', 'source_side_idx']).any()
    assert set(throws.source_event_type.unique()) <= {18, 19, 20, 22, 23}
    calculated = (np.hypot(throws.rx-throws.tx, throws.ry-throws.ty) > 40) & (throws.ry-throws.ty > 30)
    assert np.array_equal(calculated.astype(int), throws.huck)
    assert throws[['tx', 'ty', 'rx', 'ry', 'first_y']].notna().all().all()
    cutoff = throws.possession_id.map(lambda pid: by_id[pid]['first_issue']['index']
                                    if by_id[pid]['first_issue'] else np.inf)
    retained = throws[throws.source_side_idx.lt(cutoff)].copy()
    assert retained.own_possession.eq(retained.possession_id.map(possessions.own_possession)).all()
    assert retained.first_y.eq(retained.possession_id.map(possessions.first_y)).all()
    counts = retained.groupby('possession_id').size()
    for row in audit['rows']:
        assert counts.get(row['possession_id'], 0) == row['physical_throws_before_cutoff']
    retained['team_name'] = retained.possession_id.map(possessions.team_name)
    retained['outcome'] = retained.possession_id.map(possessions.outcome)
    scopes = {}
    for scope in ['long_field', 'all_starts']:
        sample = retained[retained.first_y.le(40)].copy() if scope == 'long_field' else retained.copy()
        league = summarize(sample)
        league['first_vs_all_subsequent'] = summarize(sample, 'regained', (0, 1))
        teams = []
        for tid, team in sample.groupby('team', sort=True):
            observed = summarize(team)
            observed['first_vs_all_subsequent'] = summarize(team, 'regained', (0, 1))
            exact = summarize(team[team.own_possession.le(3)], 'own_possession')['groups']
            teams.append({'team': tid, 'team_name': team.team_name.iloc[0],
                          'observed': observed, 'exact': exact})
        for i, g in enumerate(league['groups']):
            assert sum(t['observed']['groups'][i]['n'] for t in teams) == g['n']
            assert sum(t['observed']['groups'][i]['sum'] for t in teams) == g['sum']
        scopes[scope] = {'league': league, 'teams': teams,
                        'sensitivity': {
                            'exclude_possessions_containing_timeout': descriptive(sample[~sample.has_timeout]),
                            'exclude_period_ending_possessions': descriptive(sample[sample.outcome.ne('period_end')]),
                            'forward_over_40_yards': descriptive(sample, 'vertical_huck')}}
    per_game = retained.groupby(['team', 'GameID', 'own_possession', retained.first_y.le(40).rename('starts_60_plus')]).agg(
        attempts=('huck', 'size'), hucks=('huck', 'sum')).reset_index().to_dict('records')
    result = {
        'updatedOn': '2026-11-13',
        'definitions': {
            'formula': '100 × huck attempts / physical throw attempts; pooled counts, not an average of player or possession percentages.',
            'providerFormula': {'url': 'https://shownspace.com/about', 'section': '02 Throwing — HAP%',
                                'checkedOn': '2026-11-13', 'text': 'Share of all throws that are huck attempts.'},
            'huck': 'Straight-line endpoint distance >40 yards AND forward gain >30 yards. Teddy confirmed on November 13, 2026 that this is the identical ShownSpace cutoff, from the equation Braden provided. The formula and cutoff match; this research slice and saved snapshot are not the full live dashboard population.',
            'huckDefinitionProvenance': {'source': 'User confirmation in research chat, citing equation supplied by Braden at ShownSpace', 'confirmedOn': '2026-11-13', 'status': 'confirmed_by_user'},
            'attempt': 'Completed and incomplete physical passes, including drops and throwaways. Excludes pulls, stalls and non-throw events. Centering passes remain included.',
            'unit': 'Throw attempts by the original seven receiving-point players, grouped by their own first, second, or later possession within that point.',
            'lineup': 'Retain actions strictly before the audited first personnel change or uncertain/contradictory lineup record. Keep pre-change attempts even when a replacement line finishes the possession. Preserve original possession numbers.',
            'timeout': 'A timeout alone does not delete an attempt. Retain original-seven actions before the cutoff, including before a timeout/substitution and after same-seven timeouts. The earlier exclusion of timeout-containing possessions is retained as a sensitivity check.',
            'periodEnd': 'Include attempts in period-ending possessions; this throw-level denominator does not require a completed possession outcome.',
            'location': 'All starts or original first throwing location at least 60 yards from the attacking goal line (first_y <=40 on the 120-yard coordinate system). Starting location remains before any centering pass; it is a recorded throwing-location proxy, not a verified pull-catching spot. The 60-yard cutoff does not exactly match field positions.',
            'comparison': 'Second minus first. Opening baseline contains all eligible openings, not only openings followed by a second possession. Later possessions are conditional on losing the disc and recovering it with the original line.',
            'uncertainty': '10000 whole-game bootstrap draws with shared weights across possession groups. Team ranges are exploratory individual intervals, not simultaneous intervals or a ranking of proven team differences. No context model or CP model is needed for these observed counts.',
            'interpretation': 'A greater share of passes being hucks does not by itself establish earlier hucks, more possessions containing a huck, greater completion probability, fatigue or impatience.'
        },
        'scope': {'year': 2026, 'season': 'regular', 'games': int(retained.GameID.nunique()),
                  'teams': int(retained.team.nunique()), 'source_attempts': len(throws),
                  'retained_attempts': len(retained), 'excluded_attempts': len(throws)-len(retained),
                  'missing_game': '2026-07-18-PIT-CHI',
                  'attempts_in_timeout_possessions': int(retained.has_timeout.sum()),
                  'attempts_in_period_ending_possessions': int(retained.outcome.eq('period_end').sum()),
                  'pre_cutoff_attempts_in_interrupted_possessions': int(sum(r['physical_throws_before_cutoff'] for r in audit['rows'] if r['first_issue'])),
                  'source_excluded_points': cohort['excluded_points']},
        'scopes': scopes, 'game_counts': per_game,
        'inputs': {key: {'path': str(path.relative_to(REPO)), 'sha256': sha(path)} for key, path in inputs.items()},
        'environment': {'numpy': np.__version__, 'pandas': pd.__version__, 'bootstrap_draws': DRAWS, 'seed': SEED},
        'validation': {'passed': True, 'uniqueThrowKeys': True, 'huckGeometryRecalculated': True,
                       'allPossessionCountsMatchLineupAudit': True, 'teamCountsSumToLeague': True,
                       'originalPossessionNumbersAndStartingLocationsPreserved': True,
                       'sourceRawGameHashesChecked': len(audit['rawGameHashes'])}
    }
    output = ROOT / 'huck_attempt_percentage.json'
    output.write_text(json.dumps(clean(result), indent=2, allow_nan=False) + '\n')
    print(json.dumps(clean({'scope': result['scope'], 'league': {k: v['league'] for k, v in scopes.items()}}), indent=2))


if __name__ == '__main__':
    main()
