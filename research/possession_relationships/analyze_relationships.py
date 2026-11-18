"""Reproduce the two exploratory possession-relationship figures, without altering sources."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / 'research/oline_possessions'
DRAWS = 10000
SEED = 20261116


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (tuple, list, np.ndarray)):
        return [clean(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    return x


def corr(x, y):
    x, y = np.asarray(x), np.asarray(y)
    xc, yc = x - x.mean(axis=-1, keepdims=True), y - y.mean(axis=-1, keepdims=True)
    with np.errstate(invalid='ignore', divide='ignore'):
        return (xc * yc).sum(axis=-1) / np.sqrt((xc**2).sum(axis=-1) * (yc**2).sum(axis=-1))


def ci(a):
    a = np.asarray(a)
    valid = a[np.isfinite(a)]
    return np.quantile(valid, [.025, .975]).tolist() if len(valid) else None


def relation(x, y, bx, by):
    br = corr(bx, by)
    keep = np.isfinite(x) & np.isfinite(y)
    assert keep.all(), 'Do not silently change the team set.'
    slope, intercept = np.polyfit(x, y, 1)
    loo = [float(corr(np.delete(x, i), np.delete(y, i))) for i in range(len(x))]
    valid = int(np.isfinite(br).sum())
    interval = ci(br) if valid >= .95 * DRAWS else None
    return {'pearson': float(corr(x, y)), 'spearman': float(corr(pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy())),
            'ci95': interval, 'valid_bootstrap': valid,
            'ci_note': 'Interval omitted when fewer than 95% of game-resamples retain estimable rates for all 22 teams.' if interval is None else 'Percentile game-bootstrap interval, conditional on the fixed team roster; non-estimable draws omitted.',
            'teams': len(x), 'leave_one_team_out_range': [min(loo), max(loo)],
            'slope': slope, 'intercept': intercept}


def summarize(sample, teams, games, weights):
    # Array dimensions are game, team, possession stage, [possessions, goals, attempts, hucks].
    cube = np.zeros((len(games), len(teams), 2, 4), dtype=np.int64)
    gi = pd.Categorical(sample.GameID, categories=games).codes
    ti = pd.Categorical(sample.team, categories=teams).codes
    si = sample.own_possession.to_numpy(int) - 1
    for k, value in enumerate([np.ones(len(sample), int), sample.goal, sample.throws, sample.hucks]):
        np.add.at(cube[..., k], (gi, ti, si), np.asarray(value))
    count = cube.sum(0)
    boot = (weights @ cube.reshape(len(games), -1)).reshape(DRAWS, len(teams), 2, 4)

    def metrics(c):
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.stack([100*c[..., 3]/c[..., 2], 100*c[..., 1]/c[..., 0],
                             c[..., 2]/c[..., 0], c[..., 3]/c[..., 0]], axis=-1)

    rate, brate = metrics(count), metrics(boot)
    delta, bdelta = rate[:, 1] - rate[:, 0], brate[:, :, 1] - brate[:, :, 0]
    labels = ['hap', 'scoring', 'mean_throws', 'hucks_per_possession']
    rows = []
    for i, team in enumerate(teams):
        row = {'team': team, 'team_name': sample.loc[sample.team.eq(team), 'team_name'].iloc[0],
               'stages': [], 'change': {}, 'change_ci95': {}}
        for j in range(2):
            c = count[i, j]
            part = {'stage': j+1, 'possessions': c[0], 'goals': c[1], 'attempts': c[2], 'hucks': c[3],
                    'games': int((cube[:, i, j, 0] > 0).sum()), 'ci95': {}}
            for k, label in enumerate(labels):
                part[label] = rate[i, j, k]
                interval = ci(brate[:, i, j, k])
                if part['games'] < 2 or (label == 'scoring' and c[1] in {0, c[0]}) or (label == 'hap' and c[3] in {0, c[2]}):
                    interval = None
                part['ci95'][label] = interval
            row['stages'].append(part)
        for k, label in enumerate(labels):
            row['change'][label] = delta[i, k]
            row['change_ci95'][label] = ci(bdelta[:, i, k]) if all(s['ci95'][label] is not None for s in row['stages']) else None
        rows.append(row)
    correlations = {
        'hucking_vs_scoring_change': relation(delta[:, 0], delta[:, 1], bdelta[:, :, 0], bdelta[:, :, 1]),
        'throws_vs_scoring_change': relation(delta[:, 2], delta[:, 1], bdelta[:, :, 2], bdelta[:, :, 1]),
        'hucking_vs_throws_change': relation(delta[:, 0], delta[:, 2], bdelta[:, :, 0], bdelta[:, :, 2]),
        'hucking_vs_throws_first': relation(rate[:, 0, 0], rate[:, 0, 2], brate[:, :, 0, 0], brate[:, :, 0, 2]),
        'hucking_vs_throws_second': relation(rate[:, 1, 0], rate[:, 1, 2], brate[:, :, 1, 0], brate[:, :, 1, 2]),
    }
    league_counts = count.sum(0)
    league_boot = boot.sum(1)
    lr, lb = metrics(league_counts), metrics(league_boot)
    league = {'stages': [], 'change': {}, 'change_ci95': {}}
    for j in range(2):
        c = league_counts[j]
        league['stages'].append({'stage': j+1, 'possessions': c[0], 'goals': c[1], 'attempts': c[2], 'hucks': c[3],
                                 **{label: lr[j,k] for k,label in enumerate(labels)}})
    for k, label in enumerate(labels):
        league['change'][label] = lr[1,k]-lr[0,k]
        league['change_ci95'][label] = ci(lb[:,1,k]-lb[:,0,k])
    assert np.allclose(rate[:,:,0] / 100 * rate[:,:,2], rate[:,:,3])
    quadrants = {}
    for key in ['hap', 'mean_throws']:
        groups = {k: [] for k in ['upper_left', 'upper_right', 'lower_left', 'lower_right', 'on_axis']}
        for row in rows:
            x, y = row['change'][key], row['change']['scoring']
            q = ('upper' if y > 0 else 'lower') + ('_right' if x > 0 else '_left') if x != 0 and y != 0 else 'on_axis'
            groups[q].append(row['team'])
        assert sum(map(len, groups.values())) == len(teams)
        quadrants[key] = groups
    return {'teams': rows, 'correlations': correlations, 'league': league, 'quadrants': quadrants,
            'games': int(sample.GameID.nunique()), 'possessions': len(sample)}


def standardized_check(sample, teams):
    """Descriptive two-bin check; no uncertainty claim or causal adjustment."""
    rows = []
    for tid in teams:
        q = sample[sample.team.eq(tid)].copy()
        q['bin'] = (q.first_y > 20).astype(int)
        c = q.groupby(['own_possession', 'bin']).agg(P=('goal','size'), G=('goal','sum'), T=('throws','sum'), H=('hucks','sum'))
        if len(c) != 4 or (c[['P','T']] <= 0).any().any():
            continue
        wp = c.groupby('bin').P.sum().to_numpy(float); wp /= wp.sum()
        wt = c.groupby('bin').T.sum().to_numpy(float); wt /= wt.sum()
        values = []
        for stage in [1,2]:
            a = c.loc[stage].sort_index()
            values.append([100*np.dot(wt,a['H']/a['T']),100*np.dot(wp,a['G']/a['P'])])
        change=np.subtract(values[1],values[0])
        rows.append({'team':tid,'hap_change':change[0],'scoring_change':change[1],
                     'minimum_bin_possessions':int(c.P.min())})
    return {'team_count':len(rows), 'rows':rows,
            'pearson':float(corr([r['hap_change'] for r in rows],[r['scoring_change'] for r in rows])),
            'limitation':'Descriptive two-bin longitudinal standardization only; sparse regain bins, no lateral/opponent/wind adjustment, no interval. Not a causal estimate.'}


def main():
    paths = {k: SOURCE/k for k in ['original_line_scoring.json','possessions.csv','throws.csv','huck_attempt_percentage.json','special_situation_exclusions.json']}
    audit = json.loads(paths['original_line_scoring.json'].read_text())
    prior = json.loads(paths['huck_attempt_percentage.json'].read_text())
    assert audit['validation']['passed'] and prior['validation']['passed']
    for d in [audit, prior]:
        for rec in d['inputs'].values():
            assert sha(REPO/rec['path']) == rec['sha256'], rec['path']
    for gid,digest in audit['rawGameHashes'].items():
        assert sha(REPO/'research/dead_disc_study/raw_events'/(gid+'.json')) == digest
    p=pd.read_csv(paths['possessions.csv'])
    t=pd.read_csv(paths['throws.csv'])
    assert p.possession_id.is_unique
    assert not t.duplicated(['GameID','source_side','source_side_idx']).any()
    expected=((np.hypot(t.rx-t.tx,t.ry-t.ty)>40)&((t.ry-t.ty)>30)).astype(int)
    assert np.array_equal(t.huck,expected)
    assert t[['tx','ty','rx','ry']].notna().all().all()
    at=t.groupby('possession_id').agg(attempts=('huck','size'),hucks=('huck','sum'))
    assert np.array_equal(p.possession_id.map(at.attempts).fillna(0).astype(int),p.throws)
    assert np.array_equal(p.possession_id.map(at.hucks).fillna(0).astype(int),p.hucks)
    rows={r['possession_id']:r for r in audit['rows']}
    included=p.possession_id.map(lambda pid: rows[pid]['included'])
    base=p[included & p.own_possession.isin([1,2]) & p.first_y.notna()].copy()
    assert base.outcome.isin(['goal','turnover']).all() and not base.has_timeout.any()
    assert all(rows[pid]['line_eligible'] and not rows[pid]['special_situation_excluded'] for pid in base.possession_id)
    teams=sorted(base.team.unique());games=sorted(base.GameID.unique())
    assert len(teams)==22
    weights=np.random.default_rng(SEED).multinomial(len(games),np.full(len(games),1/len(games)),size=DRAWS)
    scopes={}
    for scope,sample in [('long_field',base[base.first_y<=40]),('all_starts',base)]:
        groups={}
        for outcome in ['all','goal','turnover']:
            sub=sample if outcome=='all' else sample[sample.outcome.eq(outcome)]
            groups[outcome]=summarize(sub,teams,games,weights)
        scopes[scope]=groups
    # Preserve a row-level evidence set and keep original identifiers/ordinals intact.
    cols=['possession_id','GameID','team','team_name','opponent','own_possession','outcome','goal','throws','hucks','first_x','first_y','quarter','has_timeout']
    base[cols].to_csv(ROOT/'eligible_possessions.csv',index=False)
    result={'id':'ufa-possession-relationships-20261116','updatedOn':'2026-11-16','buildStatus':'complete',
            'sourceFreshness':'Preserved ShownSpace export from October 12, 2026 and audited UFA events; no live refresh.',
            'design':json.loads((ROOT/'design.json').read_text()),'scopes':scopes,
            'start_standardized_check':standardized_check(base[base.first_y<=40],teams),
            'coverage':{'season':2026,'games':len(games),'teams':len(teams),'missing_game':'2026-07-18-PIT-CHI',
                        'unknown_start_excluded':int((included & p.own_possession.isin([1,2]) & p.first_y.isna()).sum()),
                        'third_or_later_excluded':int((included & p.own_possession.ge(3)).sum()),
                        'source_excluded_points':len(prior['scope']['source_excluded_points']),
                        'zero_throw_possessions':int(base.throws.eq(0).sum()),
                        'first_date':min(games)[:10],'last_date':max(games)[:10]},
            'bootstrap':{'draws':DRAWS,'seed':SEED,'cluster':'whole game, both teams, both stages together'},
            'inputs':{name:{'path':str(path.relative_to(REPO)),'sha256':sha(path)} for name,path in paths.items()},
            'calculation':{'path':str(Path(__file__).relative_to(REPO)),'sha256':sha(__file__)},
            'validation':{'passed':True,'raw_game_hashes_verified':len(audit['rawGameHashes']),
                          'unique_possessions':True,'unique_throw_keys':True,'huck_geometry_recalculated':True,
                          'all_possession_attempt_and_huck_counts_reconciled':True,'same_metric_cohort':True,
                          'algebraic_identity_verified':True}}
    (ROOT/'results.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False)+'\n')
    print(json.dumps(clean({'coverage':result['coverage'],'main':scopes['long_field']['all']['correlations'],
                            'league':scopes['long_field']['all']['league'],
                            'all_starts':scopes['all_starts']['all']['correlations'],
                            'standardized':result['start_standardized_check']}),indent=2))


if __name__=='__main__':
    main()
