"""First-vs-second team significance for both existing starting-location filters.

Use the same attempt-weighted means and game bootstrap as the saved comparison
check. Keep this separate from results.json so the source calculations remain
unchanged and prior inference provenance continues to resolve.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
SEED, DRAWS, BATCH, FAMILY = 20261116, 200000, 5000, 22
base_path = OUT / 'results.json'
base = json.loads(base_path.read_text())
earlier_path = OUT / 'comparison_check.json'
earlier = json.loads(earlier_path.read_text())
for rel, digest in {**base['inputs'], **earlier['inputs']}.items():
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
p = pd.read_csv(OUT / 'eligible_possessions.csv')
t = pd.read_csv(OUT / 'eligible_throws.csv')
assert p.possession_id.is_unique
assert not t.duplicated(['GameID', 'source_side', 'source_side_idx']).any()
assert t.cp.notna().all() and t.cp.between(0, 1).all()
assert len(t) == base['coverage']['eligible_attempts']
games = sorted(p.GameID.unique())
columns, metadata = [], []
for scope in ['long_field', 'all_starts']:
    eligible = p[p.first_y.le(40)] if scope == 'long_field' else p
    throws = t[t.possession_id.isin(eligible.possession_id)]
    groups = [base['scopes'][scope]['league']] + base['scopes'][scope]['teams']
    for group in groups:
        frame = throws if group['team'] == 'league' else throws[throws.team == group['team']]
        stage_games = []
        for stage in [1, 2]:
            q = frame[frame.own_possession == stage]
            agg = q.groupby('GameID').cp.agg(['sum', 'count']).reindex(games, fill_value=0)
            columns.extend([agg['sum'].to_numpy(), agg['count'].to_numpy()])
            mean = 100 * agg['sum'].sum() / agg['count'].sum()
            old = group['stages'][stage-1]['summary']
            assert np.isclose(mean, old['xcp'], atol=1e-10)
            assert len(q) == old['cp_attempts']
            stage_games.append(int(q.GameID.nunique()))
        metadata.append({'scope': scope, 'team': group['team'], 'team_name': group['team_name'],
                         'difference_pp': group['change_pp'], 'stage_games': stage_games})
matrix = np.array(columns).T
rng = np.random.default_rng(SEED)
chunks = []
for start in range(0, DRAWS, BATCH):
    w = rng.multinomial(len(games), np.full(len(games), 1 / len(games)), size=min(BATCH, DRAWS-start))
    sums = (w @ matrix).reshape(len(w), len(metadata), 4)
    with np.errstate(divide='ignore', invalid='ignore'):
        chunks.append(100 * (sums[:, :, 2]/sums[:, :, 3] - sums[:, :, 0]/sums[:, :, 1]))
boot = np.concatenate(chunks)
old_checks = {r['key']: r for r in earlier['comparisons'] if r['family'] in ['22_teams', 'league_overall']}
scopes = {scope: {'league': None, 'teams': {}} for scope in ['long_field', 'all_starts']}
for i, row in enumerate(metadata):
    finite = np.isfinite(boot[:, i])
    valid = min(row['stage_games']) >= 2 and finite.mean() >= .95
    ci = np.quantile(boot[finite, i], [.025, .975]).tolist() if valid else None
    family = FAMILY if row['team'] != 'league' else 1
    corrected = np.quantile(boot[finite, i], [.05/(2*family), 1-.05/(2*family)]).tolist() if valid else None
    row.update({'ci95_pp': ci, 'bonferroni_interval_pp': corrected,
                'nominal_excludes_zero': bool(valid and (ci[1] < 0 or ci[0] > 0)),
                'bonferroni_excludes_zero': bool(valid and (corrected[1] < 0 or corrected[0] > 0)),
                'estimable': bool(valid), 'valid_draws': int(finite.sum()), 'family_size': family})
    if row['scope'] == 'long_field':
        old_key = 'League overall' if row['team'] == 'league' else row['team_name']
        old = old_checks[old_key]
        assert np.allclose(ci, old['ci95_pp'], atol=1e-9)
        assert np.allclose(corrected, old['bonferroni_interval_pp'], atol=1e-9)
        assert row['nominal_excludes_zero'] == old['nominal_excludes_zero']
        assert row['bonferroni_excludes_zero'] == old['bonferroni_excludes_zero']
    if row['team'] == 'league':
        scopes[row['scope']]['league'] = row
    else:
        scopes[row['scope']]['teams'][row['team']] = row
for scope, values in scopes.items():
    assert len(values['teams']) == FAMILY
    values['nominal_teams'] = [r['team_name'] for r in values['teams'].values() if r['nominal_excludes_zero']]
    values['corrected_teams'] = [r['team_name'] for r in values['teams'].values() if r['bonferroni_excludes_zero']]
assert set(scopes['long_field']['nominal_teams']) == {'Atlanta Hustle', 'Carolina Flyers', 'Colorado Apex', 'Minnesota Wind Chill', 'Vegas Bighorns'}
output = {
    'date': '2026-11-16', 'status': 'complete', 'scopes': scopes,
    'definition': 'A star means the unrounded individual 95% bootstrap interval for second-minus-first mean xCP excludes zero. A star does not imply significance after correcting across 22 teams.',
    'method': '200,000 whole-game bootstrap resamples; same weights in both stages and all teams. Two-sided percentile intervals, no p-values calculated.',
    'draws': DRAWS, 'seed': SEED,
    'multiplicity': 'Bonferroni adjustment across 22 team comparisons separately within each starting-location filter. No claim of correction across every filter or earlier analysis.',
    'display': 'Whole-possession difference ranges and significance use this check. Per-throw marks and their individual intervals retain the original 10,000 draws.',
    'limitations': ['Exploratory, conditional on the selected cohort and recorded model outputs.', 'Centering retained; incomplete field-position matching; no causal interpretation.', 'Small second-possession samples can make differences and intervals unstable.'],
    'inputs': {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [base_path, earlier_path, OUT/'eligible_possessions.csv', OUT/'eligible_throws.csv', Path(__file__)]},
    'validation': {'all_means_and_counts_match_graph': True, 'long_field_inference_matches_prior_200000_draw_check': True, 'all_22_teams_in_both_filters': True, 'flags_use_unrounded_difference_intervals': True},
}
(OUT / 'team_significance.json').write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
print(json.dumps({scope: {k: v[k] for k in ['nominal_teams', 'corrected_teams']} for scope, v in scopes.items()}, indent=2))
