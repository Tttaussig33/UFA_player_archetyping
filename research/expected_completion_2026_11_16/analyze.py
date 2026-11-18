"""Observed ShownSpace xCP across first/second receiving-team possessions.

Uses the existing original-seven cohort without changing source data, film labels,
possession numbering or completion probabilities. Run with the analysis venv.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
SOURCE = REPO / 'research/oline_possessions'
SEED, DRAWS, MAX_ORDINAL = 20261116, 10000, 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def interval(values, games):
    valid = np.isfinite(values)
    if games < 2 or valid.sum() < .95 * DRAWS:
        return None
    return np.quantile(values[valid], [.025, .975]).tolist()


audit = json.loads((SOURCE / 'original_line_scoring.json').read_text())
assert audit['validation']['passed']
for record in audit['inputs'].values():
    assert sha(REPO / record['path']) == record['sha256'], record['path']
for game, digest in audit['rawGameHashes'].items():
    assert sha(REPO / 'research/dead_disc_study/raw_events' / (game + '.json')) == digest, game
source_p = pd.read_csv(SOURCE / 'possessions.csv')
source_t = pd.read_csv(SOURCE / 'throws.csv')
assert source_p.possession_id.is_unique
assert not source_t.duplicated(['GameID', 'source_side', 'source_side_idx']).any()
assert source_t.cp.dropna().between(0, 1).all()
assert source_t.source_event_type.isin([18, 19, 20, 22, 23]).all()
assert not source_t.duplicated(['possession_id', 'ordinal']).any()
included = {r['possession_id'] for r in audit['rows'] if r['included']}
p0 = source_p[source_p.possession_id.isin(included) & source_p.own_possession.isin([1, 2])].copy()
p = p0[p0.first_y.notna()].copy()
assert p.outcome.isin(['goal', 'turnover']).all() and not p.has_timeout.any()
assert p.own_possession.value_counts().to_dict() == {1: 5474, 2: 838}
t = source_t.merge(p[['possession_id']], on='possession_id', validate='many_to_one')
counts = t.groupby('possession_id').size()
assert np.array_equal(p.possession_id.map(counts).fillna(0).astype(int), p.throws)
for _, group in t.groupby('possession_id'):
    assert sorted(group.ordinal.tolist()) == list(range(1, len(group) + 1))
assert all(t.groupby('possession_id').own_possession.first() ==
           p.set_index('possession_id').own_possession.reindex(t.groupby('possession_id').size().index))

games = sorted(p.GameID.unique())
weights = np.random.default_rng(SEED).multinomial(len(games), np.full(len(games), 1 / len(games)), size=DRAWS)
names = p[['team', 'team_name']].drop_duplicates().set_index('team').team_name.to_dict()
teams = ['league'] + sorted(names, key=names.get)


def scope_result(possessions):
    throws = t[t.possession_id.isin(possessions.possession_id)]
    keys, frames, numerators, denominators = [], [], [], []
    for team in teams:
        team_throws = throws if team == 'league' else throws[throws.team == team]
        for stage in [1, 2]:
            stage_throws = team_throws[team_throws.own_possession == stage]
            for ordinal in range(MAX_ORDINAL + 1):
                q = stage_throws if ordinal == 0 else stage_throws[stage_throws.ordinal == ordinal]
                agg = q.groupby('GameID').cp.agg(['sum', 'count']).reindex(games, fill_value=0)
                keys.append((team, stage, ordinal))
                frames.append(q)
                numerators.append(agg['sum'].to_numpy())
                denominators.append(agg['count'].to_numpy())
    num, den = np.array(numerators).T, np.array(denominators).T
    with np.errstate(divide='ignore', invalid='ignore'):
        boot = 100 * (weights @ num) / (weights @ den)
    metrics, boot_columns = {}, {}
    for index, (key, frame) in enumerate(zip(keys, frames)):
        team, stage, ordinal = key
        team_p = possessions if team == 'league' else possessions[possessions.team == team]
        stage_p = team_p[team_p.own_possession == stage]
        n = int(den[:, index].sum())
        total = float(num[:, index].sum())
        n_games = frame.loc[frame.cp.notna(), 'GameID'].nunique()
        metrics[key] = {
            'ordinal': ordinal or None, 'stage': stage,
            'xcp': 100 * total / n if n else None,
            'cp_sum': total, 'cp_attempts': n, 'attempts': len(frame),
            'missing_cp': int(frame.cp.isna().sum()),
            'possessions': len(stage_p) if not ordinal else frame.possession_id.nunique(),
            'games': n_games, 'ci95': interval(boot[:, index], n_games),
            'valid_bootstrap_draws': int(np.isfinite(boot[:, index]).sum()),
        }
        boot_columns[key] = index
    output = []
    for team in teams:
        stages = []
        for stage in [1, 2]:
            summary = metrics[(team, stage, 0)]
            series = [metrics[(team, stage, i)] for i in range(1, MAX_ORDINAL + 1)]
            stages.append({'summary': summary, 'series': series,
                           'attempts_after_20': summary['attempts'] - sum(r['attempts'] for r in series)})
        first, second = (s['summary'] for s in stages)
        delta = boot[:, boot_columns[(team, 2, 0)]] - boot[:, boot_columns[(team, 1, 0)]]
        output.append({
            'team': team, 'team_name': 'League pooled' if team == 'league' else names[team],
            'stages': stages,
            'change_pp': second['xcp'] - first['xcp'] if first['xcp'] is not None and second['xcp'] is not None else None,
            'change_ci95': interval(delta, min(first['games'], second['games'])),
        })
    return {'league': output[0], 'teams': output[1:]}


long = p[p.first_y <= 40]
assert long.own_possession.value_counts().to_dict() == {1: 4802, 2: 457}
result = {
    'id': 'ufa-expected-completion-by-possession-20261116', 'updatedOn': '2026-11-16',
    'buildStatus': 'complete',
    'definition': 'Mean of stored ShownSpace completion probabilities across attempted throws, multiplied by 100. Every attempt is weighted equally; this is not an average of possession means.',
    'catalog': 'https://shownspace.com/about',
    'coverage': {
        'period': '2026 regular season, April 24–July 19', 'games': len(games), 'teams': len(names),
        'missing_game': '2026-07-18-PIT-CHI', 'unknown_start_possessions_excluded': len(p0) - len(p),
        'eligible_first_possessions': int((p.own_possession == 1).sum()),
        'eligible_second_possessions': int((p.own_possession == 2).sum()),
        'eligible_attempts': len(t), 'missing_cp': int(t.cp.isna().sum()),
        'source': 'Preserved ShownSpace export and audited UFA events; not a live website refresh.',
    },
    'cohort': 'Receiving team, original seven throughout the possession, no timeout within that possession, resolved goal or turnover, known first throwing location and existing reviewed clock exclusions. Retain all eligible opening possessions, including those never followed by a second possession. Never renumber.',
    'starts': 'Default: first recorded throw starts at least 60 yards from attacking goal (first_y <= 40). This is a broad restriction, not exact matching. Alternate: all known starts. Centering does not change the starting-location definition.',
    'centering': 'All physical attempts retained, including opening centering passes. Film labels are incomplete; no blanket or inferred deduction. Second possessions have no centering deduction.',
    'progression': 'At throw number k, average only attempts that reached k in that possession stage. Different possessions contribute at different throw numbers. Show up to 20; whole-possession means include every attempt beyond 20 as well.',
    'bootstrap': {'draws': DRAWS, 'seed': SEED, 'cluster': 'Whole game; identical weights across both teams, both stages and all throw numbers.',
                  'range': 'Pointwise percentile 95% intervals; suppressed below two contributing games or 95% estimable resamples. Intervals are not simultaneous and omit model uncertainty.'},
    'limitations': ['Descriptive comparison, not a causal effect of turnovers or fatigue.',
                   'Second possessions occur only after the receiving team loses and recovers the disc; the first and second samples are not paired.',
                   'Lower xCP means lower completion likelihood according to recorded model context, not observed failure or guaranteed deliberate risk taking.',
                   'Receiver separation and defensive pressure are not fully measured. Stored CP model version/training exclusion is not independently verified here.',
                   'Reviewed end-of-quarter exclusions cover identified cases, not a complete league-wide screen.'],
    'scopes': {'long_field': scope_result(long), 'all_starts': scope_result(p)},
    'inputs': {str(path.relative_to(REPO)): sha(path) for path in [
        SOURCE / 'throws.csv', SOURCE / 'possessions.csv', SOURCE / 'original_line_scoring.json',
        SOURCE / 'special_situation_exclusions.json', Path(__file__)]},
    'validation': {'passed': True, 'raw_game_hashes_verified': len(audit['rawGameHashes']),
                   'unique_throw_events': True, 'cp_in_range': True, 'throw_counts_reconciled': True,
                   'original_possession_numbers_preserved': True, 'consecutive_physical_ordinals': True},
}
aec_source_path = OUT / 'shownspace-team-aec-source.json'
aec_source = json.loads(aec_source_path.read_text())
assert aec_source['filters'] == {'league': 'UFA', 'season': 2026, 'view': 'Total', 'unit': 'Team', 'division': 'All'}
aec_columns = {label: i for i, label in enumerate(aec_source['headers'])}
aec_by_team = {}
for record in aec_source['rows']:
    slug = record['teamHref'].split('?')[0].split('/')[-1]
    assert slug not in aec_by_team
    aec_by_team[slug] = {
        'total_aec': float(record['cells'][aec_columns['Tot-aEC']]),
        'aec_games': int(record['cells'][aec_columns['GP']]),
        'aec_source_name': record['cells'][aec_columns['Team']],
    }
assert set(aec_by_team) == set(names)
assert all(np.isfinite(row['total_aec']) and row['aec_games'] > 0 for row in aec_by_team.values())
for scope in result['scopes'].values():
    for row in scope['teams']:
        row.update(aec_by_team[row['team']])
result['team_aec'] = {
    'source_url': aec_source['sourceUrl'], 'retrieved_on': aec_source['retrievedOn'],
    'metric': 'ShownSpace team Tot-aEC', 'filters': aec_source['filters'],
    'role': 'Sort key and displayed team total only; does not alter xCP estimates or eligibility.',
    'scope_note': 'ShownSpace 2026 season totals cover 12–15 games per team, including postseason games. xCP uses the archived regular-season cohort. These are different game windows.',
    'precision': 'Two decimal places, exactly as displayed in the Total view; not reconstructed from rounded per-game values.',
    'filter_behavior': 'Total aEC stays fixed when changing starting-location or throw-number filters.',
    'matched_teams': len(aec_by_team),
}
result['inputs'][str(aec_source_path.relative_to(REPO))] = sha(aec_source_path)
result['validation']['team_aec_exact_slug_join'] = True
(OUT / 'results.json').write_text(json.dumps(clean(result), indent=2, allow_nan=False) + '\n')
p[['possession_id', 'GameID', 'team', 'team_name', 'own_possession', 'outcome', 'throws', 'first_y']].to_csv(OUT / 'eligible_possessions.csv', index=False)
t[['possession_id', 'GameID', 'team', 'own_possession', 'ordinal', 'source_side', 'source_side_idx', 'source_event_type', 'cp', 'first_y']].to_csv(OUT / 'eligible_throws.csv', index=False)
print(json.dumps(clean({'coverage': result['coverage'], 'league': {
    key: {'first': scope['league']['stages'][0]['summary'],
          'second': scope['league']['stages'][1]['summary'],
          'change_pp': scope['league']['change_pp'], 'change_ci95': scope['league']['change_ci95']}
    for key, scope in result['scopes'].items()}}), indent=2))
