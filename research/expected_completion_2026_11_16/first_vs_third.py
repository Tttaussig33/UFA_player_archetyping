"""First versus exactly third O-line possession: same observed xCP definition.

Retain the archived original-seven cohort and centering passes. The primary
comparison uses the existing >=60-yards-from-goal filter. The all-starts view
is a sensitivity check. No edits to the dashboard, source events or labels.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
SOURCE = REPO / 'research/oline_possessions'
SEED, DRAWS, BATCH = 20261116, 200000, 5000
previous = json.loads((OUT / 'results.json').read_text())
audit = json.loads((SOURCE / 'original_line_scoring.json').read_text())
assert audit['validation']['passed']
for rel, digest in previous['inputs'].items():
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
p0 = pd.read_csv(SOURCE / 'possessions.csv')
t0 = pd.read_csv(SOURCE / 'throws.csv')
assert p0.possession_id.is_unique
assert not t0.duplicated(['GameID', 'source_side', 'source_side_idx']).any()
ids = {r['possession_id'] for r in audit['rows'] if r['included']}
p = p0[p0.possession_id.isin(ids) & p0.first_y.notna()].copy()
assert p.outcome.isin(['goal', 'turnover']).all() and not p.has_timeout.any()
t = t0[t0.possession_id.isin(p.possession_id)]
assert t.cp.notna().all() and t.cp.between(0, 1).all()
counts = t.groupby('possession_id').size()
assert np.array_equal(p.possession_id.map(counts).fillna(0).astype(int), p.throws)
games = sorted(p.GameID.unique())
assert len(games) == 131

keys, columns, rows = [], [], []
for scope in ['long_field', 'all_starts']:
    q = p[p.first_y <= 40] if scope == 'long_field' else p
    for stage in [1, 2, 3]:
        selected = q[q.own_possession == stage]
        throws = t[t.possession_id.isin(selected.possession_id)]
        by_game = throws.groupby('GameID').cp.agg(['sum', 'count']).reindex(games, fill_value=0)
        estimate = 100 * by_game['sum'].sum() / by_game['count'].sum()
        assert np.isclose(estimate, 100 * throws.cp.mean(), atol=1e-10)
        if stage in [1, 2]:
            assert np.isclose(estimate, previous['scopes'][scope]['league']['stages'][stage-1]['summary']['xcp'], atol=1e-10)
        keys.append((scope, stage))
        columns.extend([by_game['sum'].to_numpy(), by_game['count'].to_numpy()])
        rows.append({'scope': scope, 'stage': stage, 'xcp': float(estimate),
                     'possessions': len(selected), 'attempts': len(throws),
                     'games': int(throws.GameID.nunique()), 'teams': int(throws.team.nunique())})
matrix = np.array(columns).T
rng = np.random.default_rng(SEED)
boots = []
for start in range(0, DRAWS, BATCH):
    w = rng.multinomial(len(games), np.full(len(games), 1 / len(games)), size=min(BATCH, DRAWS-start))
    sums = (w @ matrix).reshape(len(w), len(keys), 2)
    with np.errstate(invalid='ignore', divide='ignore'):
        boots.append(100 * sums[:, :, 0] / sums[:, :, 1])
boot = np.concatenate(boots)
assert np.isfinite(boot).all()
for i, row in enumerate(rows):
    row['ci95'] = np.quantile(boot[:, i], [.025, .975]).tolist()
comparisons = []
for scope in ['long_field', 'all_starts']:
    first = keys.index((scope, 1))
    for stage in [2, 3]:
        later = keys.index((scope, stage))
        delta = boot[:, later] - boot[:, first]
        comparisons.append({'scope': scope, 'later_stage': stage,
            'difference_pp': rows[later]['xcp'] - rows[first]['xcp'],
            'ci95_pp': np.quantile(delta, [.025, .975]).tolist(),
            'bonferroni_two_baseline_contrasts_interval_pp': np.quantile(delta, [.0125, .9875]).tolist()})
result = {
    'date': '2026-11-16', 'status': 'Exploratory follow-up; graph unchanged.',
    'definition': 'Attempt-weighted mean stored CP × 100. Exactly third possession, not third or later. First baseline includes all eligible openings, not only points reaching three possessions.',
    'scope': 'Receiving team, recorded original seven throughout, resolved goal/turnover, no within-possession timeout, preserved reviewed clock exclusions, unchanged original ordinal.',
    'field_position': 'Main: first recorded throw at least 60 yards from goal (first_y <= 40); sensitivity: all known starts. Broad restrictions, not exact matching.',
    'centering': 'Opening centering passes retained; no inferred deduction.',
    'uncertainty': {'draws': DRAWS, 'seed': SEED, 'method': 'Whole-game percentile bootstrap; identical game weights across stages and scopes.',
        'multiplicity': 'Alongside individual 95% intervals, 97.5% intervals give a Bonferroni adjustment for two league-wide baseline contrasts: first vs second and first vs third, separately within each scope. This is exploratory and does not correct all analyses in the project.'},
    'limitations': ['Third possessions occur only after multiple turnovers and returns of possession, so the sample is selected.',
                    'These differences do not establish fatigue or intentional risk taking. Model uncertainty and unmeasured defensive context are not included.',
                    'The small third-possession sample does not support confident generalization to every team.'],
    'stages': rows, 'comparisons': comparisons,
    'validation': {'source_hashes_verified': True, 'unique_events': True, 'throw_counts_reconcile': True, 'first_and_second_means_match_graph': True, 'all_resamples_estimable': True},
    'inputs': {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [SOURCE/'possessions.csv', SOURCE/'throws.csv', SOURCE/'original_line_scoring.json', OUT/'results.json', Path(__file__)]},
}
(OUT / 'first_vs_third.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
print(json.dumps({'stages': rows, 'comparisons': comparisons}, indent=2))
