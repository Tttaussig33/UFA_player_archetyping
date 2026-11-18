"""Exploratory team checks: first vs exactly third, default long-field cohort.

Match the existing graph's whole-game bootstrap and interval-estimability rules.
Bonferroni covers all 22 team contrasts. With very few third-possession games,
conditional finite-draw intervals are only diagnostic: missing bootstrap draws
can exceed the tail probability needed by the multiple-comparison interval.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
SOURCE = REPO / 'research/oline_possessions'
SEED, DRAWS, BATCH, FAMILY = 20261116, 200000, 5000, 22
previous = json.loads((OUT / 'results.json').read_text())
league = json.loads((OUT / 'first_vs_third.json').read_text())
audit = json.loads((SOURCE / 'original_line_scoring.json').read_text())
for rel, digest in previous['inputs'].items():
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
assert audit['validation']['passed']
p0 = pd.read_csv(SOURCE / 'possessions.csv')
t0 = pd.read_csv(SOURCE / 'throws.csv')
assert p0.possession_id.is_unique
assert not t0.duplicated(['GameID', 'source_side', 'source_side_idx']).any()
ids = {row['possession_id'] for row in audit['rows'] if row['included']}
p_all = p0[p0.possession_id.isin(ids) & p0.first_y.notna()]
games = sorted(p_all.GameID.unique())
p = p_all[p_all.first_y.le(40) & p_all.own_possession.isin([1, 3])]
t = t0[t0.possession_id.isin(p.possession_id)]
assert t.cp.notna().all() and t.cp.between(0, 1).all()
assert not p.has_timeout.any() and p.outcome.isin(['goal', 'turnover']).all()
counts = t.groupby('possession_id').size()
assert np.array_equal(p.possession_id.map(counts).fillna(0).astype(int), p.throws)
assert p.own_possession.value_counts().to_dict() == {1: 4802, 3: 64}
assert t.own_possession.value_counts().to_dict() == {1: 39228, 3: 348}
teams = previous['scopes']['long_field']['teams']
columns, rows = [], []
for team in teams:
    summaries = []
    for stage in [1, 3]:
        ps = p[(p.team == team['team']) & (p.own_possession == stage)]
        ts = t[t.possession_id.isin(ps.possession_id)]
        aggregate = ts.groupby('GameID').cp.agg(['sum', 'count']).reindex(games, fill_value=0)
        columns.extend([aggregate['sum'].to_numpy(), aggregate['count'].to_numpy()])
        mean = float(100 * ts.cp.mean()) if len(ts) else None
        if stage == 1:
            assert np.isclose(mean, team['stages'][0]['summary']['xcp'], atol=1e-10)
        summaries.append({'stage': stage, 'xcp': mean, 'possessions': len(ps),
                          'attempts': len(ts), 'games': int(ts.GameID.nunique())})
    rows.append({'team': team['team'], 'team_name': team['team_name'], 'stages': summaries,
                 'difference_pp': summaries[1]['xcp'] - summaries[0]['xcp'] if summaries[1]['xcp'] is not None else None})
matrix = np.array(columns).T
rng = np.random.default_rng(SEED)
chunks = []
for start in range(0, DRAWS, BATCH):
    w = rng.multinomial(len(games), np.full(len(games), 1 / len(games)), size=min(BATCH, DRAWS-start))
    sums = (w @ matrix).reshape(len(w), len(rows), 4)
    with np.errstate(divide='ignore', invalid='ignore'):
        chunks.append(100 * (sums[:, :, 2]/sums[:, :, 3] - sums[:, :, 0]/sums[:, :, 1]))
boot = np.concatenate(chunks)
tail = .05 / (2 * FAMILY)
for i, row in enumerate(rows):
    finite = np.isfinite(boot[:, i])
    row['valid_draws'] = int(finite.sum())
    row['unestimable_fraction'] = float(1 - finite.mean())
    valid = row['stages'][1]['games'] >= 2 and finite.mean() >= .95
    row['meets_existing_interval_display_rule'] = bool(valid)
    row['ci95_pp'] = np.quantile(boot[finite, i], [.025, .975]).tolist() if valid else None
    row['bonferroni_conditional_interval_pp'] = np.quantile(boot[finite, i], [tail, 1-tail]).tolist() if valid else None
    row['nominal_excludes_zero'] = bool(valid and (row['ci95_pp'][1] < 0 or row['ci95_pp'][0] > 0))
    row['bonferroni_conditional_excludes_zero'] = bool(valid and (row['bonferroni_conditional_interval_pp'][1] < 0 or row['bonferroni_conditional_interval_pp'][0] > 0))
    row['missing_draw_mass_exceeds_bonferroni_tail'] = bool(row['unestimable_fraction'] > tail)
    row['reason_if_suppressed'] = None if valid else ('No eligible third-possession throws' if not row['stages'][1]['attempts'] else 'Too few third-possession games / too many empty bootstrap samples')
result = {
    'date': '2026-11-16', 'status': 'Exploratory team check; no chart or source-data edits.',
    'contrast': 'Attempt-weighted stored xCP, exactly third minus first possession.',
    'scope': 'Starts at least 60 yards from goal; recorded original seven; existing resolved no-timeout cohort; original stage numbers and centering passes retained.',
    'method': 'Whole-game percentile bootstrap, identical weights across teams and stages. Bonferroni family: 22 team comparisons; no p-values calculated.',
    'bootstrap_draws': DRAWS, 'seed': SEED, 'family_size': FAMILY,
    'existing_display_rule': 'At least two contributing games in both stages and at least 95% estimable resamples.',
    'sparse_data_warning': 'Reported conditional intervals discard empty resamples. At the much stricter Bonferroni tails, missing-draw mass is material. Do not turn a conditional interval into a confident team-level finding; each third-possession sample spans at most five games.',
    'validation': {'all_22_teams_included': len(rows)==22, 'source_hashes_verified': True, 'first_estimates_match_graph': True, 'third_total_64_possessions_348_throws': True},
    'comparisons': rows,
    'inputs': {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [SOURCE/'possessions.csv', SOURCE/'throws.csv', SOURCE/'original_line_scoring.json', OUT/'results.json', OUT/'first_vs_third.json', Path(__file__)]},
}
(OUT / 'first_vs_third_teams.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
for r in rows:
    s=r['stages'][1]
    print(r['team_name'], 'third n/games', s['possessions'], s['games'], 'delta', r['difference_pp'], '95%', r['ci95_pp'], 'adjusted', r['bonferroni_conditional_interval_pp'], 'flags', r['nominal_excludes_zero'], r['bonferroni_conditional_excludes_zero'], 'missing', round(r['unestimable_fraction'],4))
