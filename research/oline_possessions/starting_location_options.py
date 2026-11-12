"""Location-only feasibility checks for proposed possession comparisons.

This does not change the study cohort, refit models, or compare outcomes.
Run with the existing analysis environment; source locations are the first
recorded attempt (throw or stall), not necessarily the catch/pickup location.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def main():
    source = ROOT / 'possessions.csv'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    reviewed = json.loads((ROOT / 'results.json').read_text())
    assert digest == reviewed['inputs']['possessions.csv']
    columns = ['GameID', 'team', 'team_name', 'possession_id', 'stage',
               'first_x', 'first_y', 'has_timeout']
    p = pd.read_csv(source, usecols=columns)
    p = p[~p.has_timeout].copy()
    known = p.dropna(subset=['first_x', 'first_y']).copy()
    known['yards_to_goal'] = 100 - known.first_y
    bands = [
        ('80+ yards', 80, float('inf')),
        ('60 to under 80 yards', 60, 80),
        ('40 to under 60 yards', 40, 60),
        ('Under 40 yards', -float('inf'), 40),
    ]
    counts = []
    for label, low, high in bands:
        groups = []
        for stage in (1, 2, 3):
            g = known[(known.stage == stage) & known.yards_to_goal.ge(low)
                      & known.yards_to_goal.lt(high)]
            groups.append({'stage': stage, 'n': len(g),
                           'within_10_yards_of_sideline_n': int(g.first_x.abs().ge(16.6667).sum())})
        counts.append({'band': label, 'groups': groups})
    for stage in (1, 2, 3):
        assert sum(b['groups'][stage-1]['n'] for b in counts) == int(known.stage.eq(stage).sum())

    # Check whether distinct real comparisons exist, without using outcomes.
    # These are maximum-cardinality feasible pairs, not a finalized matched
    # analysis, optimized balance design, or a claim of causal identification.
    long = known[known.yards_to_goal.ge(60)]
    teams = []
    for team, g in long.groupby('team'):
        a, b = g[g.stage == 1], g[g.stage == 2]
        delta = (b[['first_x', 'first_y']].to_numpy()[:, None, :]
                 - a[['first_x', 'first_y']].to_numpy()[None, :, :])
        allowed = (np.abs(delta) <= 5).all(2)
        distance = np.sqrt((delta**2).sum(2))
        edges = [sorted(np.flatnonzero(row).tolist(), key=lambda j: distance[i, j])
                 for i, row in enumerate(allowed)]
        paired = {}

        def assign(i, visited):
            for j in edges[i]:
                if j in visited:
                    continue
                visited.add(j)
                if j not in paired or assign(paired[j], visited):
                    paired[j] = i
                    return True
            return False

        for i in range(len(b)):
            assign(i, set())
        assert len(paired) == len(set(paired.values()))
        assert all(allowed[i, j] for j, i in paired.items())
        teams.append({'team': team, 'team_name': g.team_name.iloc[0],
                      'first_n': len(a), 'second_n': len(b),
                      'second_with_a_candidate': sum(bool(e) for e in edges),
                      'distinct_pairs': len(paired)})
    result = {
        'reviewed_on': '2026-11-10',
        'status': 'Comparison options only; no final definition adopted.',
        'source': 'possessions.csv', 'source_sha256': digest,
        'filters': 'Exclude possessions containing recorded timeouts; retain original stage numbers. Location comparisons exclude unknown first-attempt coordinates. No goal, turnover, huck, or eventual-hold outcome used for pairing.',
        'coordinate_definition': 'Yards to attacking goal line = 100 - first_y in the preserved normalized coordinates; signed first_x retains left/right position.',
        'stage_counts': [{'stage': s, 'all_n': int(p.stage.eq(s).sum()),
                          'known_location_n': int(known.stage.eq(s).sum())} for s in (1, 2, 3)],
        'bands': counts,
        'illustrative_pairing': {
            'definition': 'Both starts 60+ yards from goal, same team, at most five yards difference in each coordinate; one-to-one without replacement. Other game context not yet matched.',
            'first_n': sum(t['first_n'] for t in teams),
            'second_n': sum(t['second_n'] for t in teams),
            'second_with_a_candidate': sum(t['second_with_a_candidate'] for t in teams),
            'distinct_pairs': sum(t['distinct_pairs'] for t in teams),
            'teams': teams,
        },
        'limitations': ['Starting coordinates do not identify setup/centering passes.',
                        'Pair feasibility alone does not establish balance in all recorded context or comparable defensive situations.',
                        'Small within-team samples and correlated possessions require appropriate uncertainty analysis before conclusions.'],
    }
    (ROOT / 'starting_location_options.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result['illustrative_pairing'][k] for k in ['first_n', 'second_n', 'second_with_a_candidate', 'distinct_pairs']}))


if __name__ == '__main__':
    main()
