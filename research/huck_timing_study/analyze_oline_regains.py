"""Exploratory 2026 receiving-team huck choice before and after regaining the disc.

All source files are preserved, hash-checked inputs. No production values change.
Primary denominator: physical throws with valid locations, excluding stalls.
Point-start receiving role is used; this does not assert unchanged personnel.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'oline_regains'
SOURCE = Path('/Users/teddytaussig/Desktop/Work/UFA_player_archetyping/data/database-exports/2026-10-12')
RAW = ROOT.parent / 'dead_disc_study/raw_events'
sys.path.insert(0, str(ROOT.parent / 'dead_disc_study'))
from audit_restarts import matched, number, sha

ATTEMPTS = {18, 19, 20, 22, 23, 24}
LOSSES = {20, 22, 24}
GAINS = {11, 13, 14}
PERIOD_ENDS = {28, 29, 30, 31, 32, 33, 34, 35}
BOOTSTRAPS = 10000
SEED = 20261105


def read_csv(name):
    with (SOURCE / (name + '.csv')).open(newline='') as f:
        yield from csv.DictReader(f)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build_cohort():
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for name in ['games', 'teams', 'throws']:
        assert sha(SOURCE / (name + '.csv')) == manifest['tables'][name]['sha256']
    games = {r['GameID']: r for r in read_csv('games') if r['Year'] == '2026'
             and r['RegularSeasonWeek'] and not r['PlayoffRound'] and r['is_final'] == 'true'}
    names = {r['TeamID']: r['FullName'] for r in read_csv('teams') if r['Year'] == '2026'}
    stored = {}
    for r in read_csv('throws'):
        if r['GameID'] in games:
            k = (r['GameID'], r['source_side'], int(r['source_side_idx']))
            assert k not in stored
            stored[k] = r
    raw_receipt = json.loads((RAW / 'source_receipt.json').read_text())
    ambiguous = {tuple(r['context']) for r in json.loads(
        (ROOT.parent / 'pull_centering_study/results.json').read_text())['duplicate_opening_contexts']}
    points = []
    checks = Counter()
    for gid, game in sorted(games.items()):
        path = RAW / (gid + '.json')
        if not path.exists():
            assert gid == '2026-07-18-PIT-CHI'
            assert not any(k[0] == gid for k in stored)
            checks['games_missing_export_and_capture'] += 1
            continue
        assert sha(path) == raw_receipt[gid]['sha256']
        raw = json.loads(path.read_text())['data']
        for side in ['home', 'away']:
            team = game['HomeTeamID' if side == 'home' else 'AwayTeamID']
            point = pos = None
            for idx, e in enumerate(raw[side + 'Events']):
                typ = e['type']
                if typ in {1, 2}:
                    if point is not None:
                        point['errors'].add('missing_point_end_before_next_start')
                    point = pos = None
                    if typ == 2:
                        point = {'id': f'{gid}|{side}|{idx}', 'game': gid, 'side': side, 'team': team,
                                 'start_idx': idx, 'errors': set(), 'possessions': [], 'markers': [],
                                 'losses': 0, 'turnovers': 0, 'ended': None}
                        points.append(point)
                        pos = {'id': point['id'] + '|1', 'number': 1, 'start_idx': idx,
                               'attempts': [], 'end': None, 'prior_team_losses': 0}
                        point['possessions'].append(pos)
                    continue
                if point is None:
                    continue
                if typ in {3, 5, 25}:
                    point['markers'].append(idx)
                elif typ == 21:
                    point['errors'].add('dropped_pull')
                    point['losses'] += 1
                    point['turnovers'] += 1
                    if pos is not None:
                        pos['end'] = 'dropped_pull'
                    pos = None
                elif typ in GAINS:
                    if pos is not None or point['losses'] == 0:
                        point['errors'].add('gain_without_recorded_own_loss')
                    point['turnovers'] += 1
                    pn = len(point['possessions']) + 1
                    pos = {'id': point['id'] + '|' + str(pn), 'number': pn, 'start_idx': idx,
                           'attempts': [], 'end': None, 'prior_team_losses': point['losses']}
                    point['possessions'].append(pos)
                elif typ in ATTEMPTS:
                    if pos is None:
                        point['errors'].add('attempt_without_possession_start')
                        continue
                    ordinal = len(pos['attempts']) + 1
                    r = stored.get((gid, side, idx))
                    row_errors = []
                    if r is None or not matched(r, e):
                        row_errors.append('missing_or_changed_export_attempt')
                    else:
                        context = tuple(r[k] for k in ['GameID', 'source_side', 'game_quarter', 'quarter_point'])
                        if context in ambiguous:
                            row_errors.append('duplicate_opening_context')
                        if r['start_on_offense'] != 'true':
                            row_errors.append('receiving_role_mismatch')
                        if number(r['possession_throw']) != ordinal:
                            row_errors.append('throw_ordinal_mismatch')
                        if number(r['possession_num']) != point['turnovers'] + 1:
                            row_errors.append('possession_number_mismatch')
                        if number(r['turnover']) != int(typ in {20, 22, 23, 24}):
                            row_errors.append('turnover_flag_mismatch')
                        if number(r['DroppedThrow']) != int(typ == 20):
                            row_errors.append('drop_flag_mismatch')
                        if number(r['stall']) != int(typ == 24):
                            row_errors.append('stall_flag_mismatch')
                        if typ != 24:
                            xy = [number(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
                            if any(n is None for n in xy):
                                row_errors.append('missing_coordinates')
                            elif not (abs(xy[0]) <= 26.67000001 and abs(xy[2]) <= 26.67000001
                                      and 0 <= xy[1] <= 120 and 0 <= xy[3] <= 120):
                                row_errors.append('coordinates_outside_field')
                    point['errors'].update(row_errors)
                    pos['attempts'].append({'stored': r, 'event': e, 'ordinal': ordinal, 'idx': idx,
                                            'marker_before': any(j < idx for j in point['markers'])})
                    if typ in LOSSES:
                        pos['end'] = typ
                        point['losses'] += 1
                        point['turnovers'] += 1
                        pos = None
                    elif typ in {19, 23}:
                        pos['end'] = typ
                        point['ended'] = 'hold' if typ == 19 else 'break'
                        pos = point = None
                elif typ in {12, 15} | PERIOD_ENDS:
                    if pos is not None:
                        pos['end'] = typ
                        if typ in {12, 15}:
                            point['errors'].add('opponent_score_while_own_possession_active')
                    point['ended'] = 'break' if typ == 15 else ('hold' if typ == 12 else 'period_end')
                    pos = point = None
                elif typ not in {4, 6, 9, 10, 16, 17, 26, 27}:
                    point['errors'].add('unhandled_event_' + str(typ))
            if point is not None:
                point['errors'].add('unclosed_point_at_end_of_source')
    throws, possessions, exclusions = [], [], []
    for point in points:
        if point['errors']:
            checks['excluded_receiving_points'] += 1
            for error in point['errors']:
                checks['point_error_' + error] += 1
            checks['raw_attempts_in_excluded_points'] += sum(len(p['attempts']) for p in point['possessions'])
            exclusions.append({'point_id': point['id'], 'reasons': sorted(point['errors'])})
            continue
        checks['included_receiving_points'] += 1
        for pos in point['possessions']:
            assert pos['end'] is not None
            rr = []
            for a in pos['attempts']:
                r, e = a['stored'], a['event']
                if e['type'] == 24:
                    checks['stalls_excluded_from_physical_throw_denominator'] += 1
                    continue
                tx, ty, rx, ry = [float(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
                distance, forward = math.hypot(rx - tx, ry - ty), ry - ty
                huck = int(distance > 40 and forward > 30)
                t = {'GameID': point['game'], 'team': point['team'], 'team_name': names[point['team']],
                     'point_id': point['id'], 'possession_id': pos['id'], 'source_side': point['side'],
                     'source_side_idx': a['idx'], 'throw_sig_id': r['throw_sig_id'],
                     'Thrower': r['Thrower'], 'quarter': int(r['game_quarter']),
                     'regained': int(pos['number'] > 1), 'attacking_possession': pos['number'],
                     'prior_team_losses': pos['prior_team_losses'], 'ordinal': a['ordinal'],
                     'tx': tx, 'ty': ty, 'rx': rx, 'ry': ry, 'distance': distance, 'forward': forward,
                     'huck': huck, 'ufa_vertical_huck': int(forward > 40),
                     'complete': int(e['type'] in {18, 19}), 'drop': int(e['type'] == 20),
                     'assist': int(e['type'] == 19), 'cp': number(r['cp']),
                     'thrower_aec': 0.0 if e['type'] == 20 else number(r['aec']),
                     'marker_before': a['marker_before'], 'point_has_marker': bool(point['markers']),
                     'point_outcome': point['ended']}
                rr.append(t)
                throws.append(t)
            if rr:
                possessions.append({'GameID': point['game'], 'team': point['team'], 'team_name': names[point['team']],
                                    'point_id': point['id'], 'possession_id': pos['id'],
                                    'regained': int(pos['number'] > 1), 'attacking_possession': pos['number'],
                                    'throws': len(rr), 'hucks': sum(t['huck'] for t in rr),
                                    'has_huck': int(any(t['huck'] for t in rr)), 'first_y': rr[0]['ty'],
                                    'point_has_marker': bool(point['markers'])})
            else:
                checks['possessions_without_physical_throws'] += 1
    c, p = pd.DataFrame(throws), pd.DataFrame(possessions)
    assert not c.duplicated(['GameID', 'throw_sig_id']).any()
    assert c.groupby('possession_id').ordinal.min().eq(1).all()
    assert c[c.regained.eq(1)].prior_team_losses.ge(1).all()
    assert c[c.regained.eq(0)].attacking_possession.eq(1).all()
    c.to_csv(OUT / 'throw_cohort.csv', index=False)
    p.to_csv(OUT / 'possession_cohort.csv', index=False)
    dump('cohort_audit.json', {'source_receiving_points': len(points), 'checks': dict(checks),
                             'excluded_points': exclusions, 'throws': len(c), 'possessions_with_throws': len(p),
                             'games': c.GameID.nunique(), 'teams': c.team.nunique(),
                             'inputs': {str(SOURCE / (n + '.csv')): manifest['tables'][n]['sha256'] for n in ['games', 'teams', 'throws']},
                             'raw_receipt': str(RAW / 'source_receipt.json'),
                             'policy': 'Exclude entire receiving point for any source, sequence, outcome, or coordinate inconsistency; dropped-pull points excluded. No filtering by eventual hold/break.'})
    return c, p


def ci(values):
    values = np.asarray(values)
    good = values[np.isfinite(values)]
    return {'low': float(np.quantile(good, .025)), 'high': float(np.quantile(good, .975)),
            'valid_draws': len(good)} if len(good) else None


def compare(c, outcome='huck', rng=None):
    """Paired whole-game bootstrap retains both stages and both teams in each game."""
    assert rng is not None
    g = sorted(c.GameID.unique())
    n = np.zeros((len(g), 2))
    y = np.zeros_like(n)
    gi = pd.Categorical(c.GameID, categories=g).codes
    np.add.at(n, (gi, c.regained.to_numpy(int)), 1)
    np.add.at(y, (gi, c.regained.to_numpy(int)), c[outcome].to_numpy())
    w = rng.multinomial(len(g), np.full(len(g), 1 / len(g)), size=BOOTSTRAPS)
    bn, by = w @ n, w @ y
    with np.errstate(divide='ignore', invalid='ignore'):
        b = by / bn
        ratio = b[:, 1] / b[:, 0]
    rates = y.sum(0) / n.sum(0)
    return {'opening': {'n': int(n[:, 0].sum()), 'hucks': int(y[:, 0].sum()), 'rate': float(rates[0]), 'ci95': ci(b[:, 0])},
            'regained': {'n': int(n[:, 1].sum()), 'hucks': int(y[:, 1].sum()), 'rate': float(rates[1]), 'ci95': ci(b[:, 1])},
            'difference_pp': float(100 * (rates[1] - rates[0])), 'difference_ci95_pp': ci(100 * (b[:, 1] - b[:, 0])),
            'rate_ratio': float(rates[1] / rates[0]), 'rate_ratio_ci95': ci(ratio), 'games': len(g)}


def logistic_adjustment(c, ordinal=False):
    """Binomial logit with natural cubic release-Y spline and game-cluster covariance.

    Adjustment is descriptive standardization, not a causal intervention.
    The chosen throw's CP, endpoint, completion, and future point outcome are not controls.
    """
    original_n = len(c)
    # A >30-yard forward throw cannot remain in bounds from Y >=90.
    # Exclude that structural-zero region from the adjusted association only.
    c = c[c.ty.lt(90)].copy()
    y = c.huck.to_numpy(float)
    z = c.ty.to_numpy() / 90
    knots = np.array([0, 15, 30, 45, 60, 75, 90]) / 90
    def d(k):
        return (np.maximum(z - k, 0) ** 3 - np.maximum(z - knots[-1], 0) ** 3) / (knots[-1] - k)
    columns = [np.ones(len(c)), c.regained.to_numpy(float), z]
    labels = ['intercept', 'regained', 'release_y']
    for k in knots[:-2]:
        columns.append(d(k) - d(knots[-2])); labels.append('release_y_spline_' + str(k))
    x = c.tx.abs().to_numpy() / 26.67
    columns += [x, x*x]
    labels += ['abs_release_x', 'abs_release_x_squared']
    for team in sorted(c.team.unique())[1:]:
        columns.append(c.team.eq(team).to_numpy(float)); labels.append('team_' + team)
    if ordinal:
        ln = np.log1p(c.ordinal.to_numpy(float))
        columns += [ln, ln*ln]
        labels += ['log_throw_ordinal', 'log_throw_ordinal_squared']
    X = np.column_stack(columns)
    scales = X.std(axis=0); scales[:2] = 1
    assert (scales > 0).all()
    X = X / scales
    beta = np.zeros(X.shape[1]); beta[0] = math.log(y.mean() / (1 - y.mean()))
    def loglike(b):
        eta = X @ b
        return float(np.sum(y * eta - np.logaddexp(0, eta)))
    history = [loglike(beta)]
    for iteration in range(100):
        pred = 1 / (1 + np.exp(-np.clip(X @ beta, -40, 40)))
        v = pred * (1 - pred)
        H = X.T @ (v[:, None] * X)
        score = X.T @ (y - pred)
        step = np.linalg.solve(H, score)
        scale = 1.0
        while loglike(beta + scale * step) < history[-1] - 1e-8:
            scale /= 2
            assert scale > 1e-10
        beta += scale * step
        history.append(loglike(beta))
        if np.max(np.abs(score)) < 1e-7:
            break
    pred = 1 / (1 + np.exp(-np.clip(X @ beta, -40, 40)))
    score = X.T @ (y - pred)
    assert np.max(np.abs(score)) < 1e-5
    bread = np.linalg.inv(X.T @ ((pred * (1 - pred))[:, None] * X))
    games = sorted(c.GameID.unique())
    gi = pd.Categorical(c.GameID, categories=games).codes
    cluster_scores = np.zeros((len(games), X.shape[1]))
    np.add.at(cluster_scores, gi, X * (y - pred)[:, None])
    correction = len(games)/(len(games)-1) * (len(c)-1)/(len(c)-X.shape[1])
    covariance = bread @ (cluster_scores.T @ cluster_scores) @ bread * correction
    se = math.sqrt(covariance[1,1])
    marginal, gradients = [], []
    for state in [0, 1]:
        xx = X.copy(); xx[:,1] = state
        pp = 1 / (1 + np.exp(-np.clip(xx @ beta, -40, 40)))
        marginal.append(float(pp.mean()))
        gradients.append(np.mean(xx * (pp * (1 - pp))[:, None], axis=0))
    grad = gradients[1] - gradients[0]
    sd = math.sqrt(float(grad @ covariance @ grad))
    diff = marginal[1] - marginal[0]
    return {'adjustment': labels, 'n': len(c), 'hucks': int(y.sum()), 'game_clusters': len(games),
            'eligibility': 'Release Y below 90 yards, leaving over 30 forward yards in the 120-yard coordinate system.',
            'throws_excluded_as_no_forward_huck_space': original_n-len(c),
            'regained_odds_ratio': math.exp(beta[1]), 'odds_ratio_ci95': [math.exp(beta[1]-1.96*se), math.exp(beta[1]+1.96*se)],
            'standardized_opening_rate': marginal[0], 'standardized_regained_rate': marginal[1],
            'standardized_difference_pp': 100*diff, 'difference_ci95_pp': [100*(diff-1.96*sd),100*(diff+1.96*sd)],
            'numerical_checks': {'iterations': iteration+1,'max_absolute_score': float(np.max(np.abs(score))),
                                 'log_likelihood_nondecreasing': bool(np.min(np.diff(history)) >= -1e-8),
                                 'design_rank': int(np.linalg.matrix_rank(X)), 'columns': X.shape[1]},
            'limits': 'Exploratory model-dependent association with game-cluster robust Wald intervals. No receiver/defender, wind, or fatigue measurements. Marginal rates standardized to the observed throw-context distribution, not causal effects.'}


def main():
    # Exploratory specification; this is not a preregistration.
    OUT.mkdir(exist_ok=True)
    dump('analysis_design.json', {'question': 'Do receiving teams huck more often after losing and regaining possession than on their opening possession?',
         'primary': 'Huck attempts / all physical throws, receiving-start points, opening versus all regained attacking possessions.',
         'huck': 'Euclidean flight distance >40 yards and forward gain >30 yards.',
         'sensitivity': ['First regained possession only','First three throws only','Opening and first regain from the same points',
                         'No timeout/injury marker anywhere in point','Official UFA >40 forward yards definition'],
         'secondary': 'Possessions with at least one huck / possessions with at least one physical throw.',
         'adjustment': 'Among release Y <90 yards where the defined huck has sufficient forward field space, logistic regression of huck choice on regained status, release-Y natural cubic spline with fixed 15-yard knots from 0 to 90, absolute release-X and its square, and team indicators. Additional sensitivity includes log throw ordinal and its square.',
         'uncertainty': {'whole_game_bootstrap_draws': BOOTSTRAPS, 'seed': SEED, 'team_intervals': 'Exploratory, only 11 or 12 game clusters per team; no multiple-testing-adjusted ranking.'},
         'post_result_checks': ['First-three-throw comparison repeated with the official >40-forward-yard huck definition.'],
         'scope': '2026 final regular season in preserved export; one game missing. Exploratory retrospective analysis.'})
    c, p = build_cohort()
    rng = np.random.default_rng(SEED)
    league = compare(c, rng=rng)
    teams = []
    for team, q in c.groupby('team', sort=True):
        record = {'team': team, 'team_name': q.team_name.iloc[0], **compare(q, rng=rng)}
        teams.append(record)
    regained_point_ids = set(p[p.attacking_possession.eq(2)].point_id)
    sensitivity = {
        'first_regain_only': compare(c[c.attacking_possession.le(2)], rng=rng),
        'first_three_throws': compare(c[c.ordinal.le(3)], rng=rng),
        'same_points_opening_and_first_regain': compare(c[c.point_id.isin(regained_point_ids) & c.attacking_possession.le(2)], rng=rng),
        'no_timeout_or_injury_markers': compare(c[~c.point_has_marker], rng=rng),
        'official_vertical_definition': compare(c, outcome='ufa_vertical_huck', rng=rng),
        # Follow-up robustness check after inspecting the initial exploratory comparison.
        'first_three_official_vertical_definition': compare(c[c.ordinal.le(3)], outcome='ufa_vertical_huck', rng=np.random.default_rng(40119)),
    }
    by_stage = []
    for label, mask in [('1', c.ordinal.eq(1)),('2–3', c.ordinal.between(2,3)),('4–6', c.ordinal.between(4,6)),('7+', c.ordinal.ge(7))]:
        by_stage.append({'stage': label, **compare(c[mask], rng=rng)})
    huck_outcomes = []
    for regained, q in c[c.huck.eq(1)].groupby('regained'):
        complete_cp = q[q.cp.notna() & q.cp.between(0,1)]
        huck_outcomes.append({'regained': int(regained), 'hucks': len(q), 'completions': int(q.complete.sum()),
                              'completion_rate': float(q.complete.mean()), 'drops': int(q['drop'].sum()),
                              'cp_n': len(complete_cp), 'mean_cp': float(complete_cp.cp.mean()),
                              'credited_cpoe_pp': float(100*(complete_cp.complete + complete_cp['drop'] - complete_cp.cp).mean()),
                              'assists': int(q.assist.sum()), 'total_thrower_aec': float(q.thrower_aec.sum())})
    result = {'status':'Exploratory observed associations, not a causal test of fatigue or impatience.',
              'league':league, 'teams':teams, 'possession_level':compare(p,outcome='has_huck',rng=rng),
              'mean_throws_per_possession': {str(k):float(q.throws.mean()) for k,q in p.groupby('regained')},
              'mean_release_y': {str(k):float(q.ty.mean()) for k,q in c.groupby('regained')},
              'stage_comparison':by_stage,'sensitivity':sensitivity,
              'adjusted':logistic_adjustment(c), 'adjusted_with_throw_ordinal':logistic_adjustment(c,ordinal=True),
              'huck_outcomes_supporting':huck_outcomes,
              'source_manifest':str(SOURCE/'manifest.json'), 'cohort_audit':str(OUT/'cohort_audit.json'),
              'limitations':['A receiving-start team may change personnel at a timeout or injury; no-marker sensitivity provided.',
                             'Regained possessions follow selected failures and field transitions; comparisons do not isolate causal effects of a turnover.',
                             'Actual elapsed playing time is not established by stored per-throw clocks.',
                             'Team-level comparisons are exploratory and use only 11 or 12 games; uncertainty intervals are unadjusted for multiple comparisons.',
                             'Initial failed possessions are selected by outcome in the same-point sensitivity; that result is not a causal within-point estimate.',
                             'Missing game: 2026-07-18-PIT-CHI. No new live database query was performed.']}
    dump('results.json', result)
    pd.DataFrame([{'team':r['team'],'team_name':r['team_name'],'games':r['games'],
                   'opening_throws':r['opening']['n'],'opening_hucks':r['opening']['hucks'],'opening_rate':r['opening']['rate'],
                   'regained_throws':r['regained']['n'],'regained_hucks':r['regained']['hucks'],'regained_rate':r['regained']['rate'],
                   'difference_pp':r['difference_pp'],'difference_low_pp':r['difference_ci95_pp']['low'],
                   'difference_high_pp':r['difference_ci95_pp']['high']} for r in teams]).to_csv(OUT/'team_results.csv',index=False)
    print(json.dumps({k:result[k] for k in ['league','possession_level','mean_throws_per_possession','mean_release_y','adjusted','adjusted_with_throw_ordinal','sensitivity']},indent=2))


if __name__ == '__main__':
    main()
