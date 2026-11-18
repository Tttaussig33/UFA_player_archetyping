"""Exploratory inference for the existing default xCP graph; no chart edits.

Two-sided differences (second minus first), unchanged attempt weighting and
cohort. Whole-game percentile bootstrap. Family A: 22 whole-possession team
comparisons. Family B: 12 pooled-league throw-number comparisons. Each family
receives a separate Bonferroni adjustment; no joint claim across both families.
These families were specified after inspecting the existing graph. Approximate
bootstrap intervals are not a replacement for small-cluster validation.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SEED, DRAWS, BATCH = 20261116, 200000, 5000
data = json.loads((ROOT / 'results.json').read_text())
for rel, digest in data['inputs'].items():
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
p = pd.read_csv(ROOT / 'eligible_possessions.csv')
t = pd.read_csv(ROOT / 'eligible_throws.csv')
assert p.possession_id.is_unique
assert not t.duplicated(['GameID', 'source_side', 'source_side_idx']).any()
assert t.cp.notna().all() and t.cp.between(0, 1).all()
assert len(t) == data['coverage']['eligible_attempts']
games = sorted(p.GameID.unique())
long_ids = set(p.loc[p.first_y <= 40, 'possession_id'])
t = t[t.possession_id.isin(long_ids)]
records = data['scopes']['long_field']['teams']
keys, matrices, metadata = [], [], []


def add_comparison(key, frame, first_record, second_record, family):
    sums = []
    for stage in [1, 2]:
        q = frame[frame.own_possession == stage]
        a = q.groupby('GameID').cp.agg(['sum', 'count']).reindex(games, fill_value=0)
        sums.extend([a['sum'].to_numpy(), a['count'].to_numpy()])
    sums = np.array(sums).T
    total = sums.sum(0)
    difference = 100 * (total[2] / total[3] - total[0] / total[1])
    assert np.isclose(difference, second_record['xcp'] - first_record['xcp'], atol=1e-10)
    keys.append(key)
    matrices.append(sums)
    metadata.append({'key': key, 'family': family, 'change_pp': float(difference),
                     'first_throws': int(total[1]), 'second_throws': int(total[3]),
                     'first_games': first_record['games'], 'second_games': second_record['games']})


for row in records:
    add_comparison(row['team_name'], t[t.team == row['team']],
                   row['stages'][0]['summary'], row['stages'][1]['summary'], '22_teams')
league = data['scopes']['long_field']['league']
for i in range(12):
    add_comparison('Throw ' + str(i + 1), t[t.ordinal == i + 1],
                   league['stages'][0]['series'][i], league['stages'][1]['series'][i], '12_throw_numbers')
add_comparison('League overall', t, league['stages'][0]['summary'], league['stages'][1]['summary'], 'league_overall')

matrix = np.concatenate(matrices, axis=1)
rng = np.random.default_rng(SEED)
differences = []
for start in range(0, DRAWS, BATCH):
    w = rng.multinomial(len(games), np.full(len(games), 1 / len(games)), size=min(BATCH, DRAWS-start))
    b = (w @ matrix).reshape(len(w), len(keys), 4)
    with np.errstate(divide='ignore', invalid='ignore'):
        differences.append(100 * (b[:, :, 2] / b[:, :, 3] - b[:, :, 0] / b[:, :, 1]))
boot = np.concatenate(differences, axis=0)
original_ranges = {r['team_name']: r['change_ci95'] for r in records}
original_ranges['League overall'] = league['change_ci95']
for i, key in enumerate(keys):
    if key in original_ranges:
        original_draws = boot[:10000, i]
        original_draws = original_draws[np.isfinite(original_draws)]
        assert np.allclose(np.quantile(original_draws, [.025, .975]), original_ranges[key], atol=1e-9), key
for i, row in enumerate(metadata):
    finite = np.isfinite(boot[:, i])
    row['valid_draws'] = int(finite.sum())
    assert row['valid_draws'] >= .95 * DRAWS
    values = boot[finite, i]
    family_size = {'22_teams': 22, '12_throw_numbers': 12, 'league_overall': 1}[row['family']]
    alpha = .05 / family_size
    row['ci95_pp'] = np.quantile(values, [.025, .975]).tolist()
    row['bonferroni_interval_pp'] = np.quantile(values, [alpha / 2, 1 - alpha / 2]).tolist()
    row['bonferroni_individual_confidence'] = 1 - alpha
    row['nominal_excludes_zero'] = bool(row['ci95_pp'][1] < 0 or row['ci95_pp'][0] > 0)
    row['bonferroni_excludes_zero'] = bool(row['bonferroni_interval_pp'][1] < 0 or row['bonferroni_interval_pp'][0] > 0)
output = {
    'date': '2026-11-16', 'status': 'Exploratory interval-based comparison; not a t-test or a p-value calculation.',
    'scope': 'Default graph: starts at least 60 yards from goal; recorded original seven; centering retained.',
    'null': 'Second-possession minus first-possession mean stored xCP equals zero.',
    'method': 'Whole-game percentile bootstrap; same game weights for both teams, stages and throw numbers. Attempt-weighted means exactly match the graph.',
    'draws': DRAWS, 'seed': SEED, 'games': len(games),
    'validation': {'all_point_estimates_match_graph': True, 'first_10000_draws_reproduce_23_original_difference_intervals': True},
    'multiplicity': 'Bonferroni intervals within 22 team comparisons, or separately within 12 pooled throw-number comparisons. Families inspected after prior graph results. Does not cover every team-by-throw view, alternate start filter or prior analysis in the project.',
    'limits': ['Approximate intervals inherit bootstrap assumptions. Some team estimates have only 6–12 games with second possessions.',
               'Resampling quantiles can be unstable near zero; no binary finding should obscure its interval, sample size or sensitivity.',
               'Centering passes and differences in starting location remain. No causal or fatigue interpretation. Model uncertainty is excluded.',
               'These are differences in expected completion, not tests of actual catches or of total aEC.'],
    'references': ['https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm',
                   'https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm'],
    'inputs': {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'results.json', ROOT/'eligible_possessions.csv', ROOT/'eligible_throws.csv', Path(__file__)]},
    'comparisons': metadata,
}
(ROOT / 'comparison_check.json').write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
print(json.dumps({'nominal': [r for r in metadata if r['nominal_excludes_zero']],
                  'adjusted': [r for r in metadata if r['bonferroni_excludes_zero']]}, indent=2))
