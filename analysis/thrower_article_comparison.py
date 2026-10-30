"""Describe complete passing profiles against the UFA June 23 article.

Read-only preserved exports. This is an exploratory descriptive study, not a
fitted archetype classifier or a claim of transferable skill. Reproduce with the
bundled Python environment (NumPy/pandas). No website or raw data is modified.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'data/database-exports/2026-10-12'
ARTICLE = 'https://watchufa.com/league/news/2026-ufa-breaking-down-important-passers-thrower-types-janas-hawkins-edmonds-van-deusen'
EXAMPLES = ['ehawkins', 'tedmonds', 'pjanas', 'bvandeuse', 'ataylor', 'jnissen']
TRAITS = ['shortShare', 'huckShare', 'forwardShare', 'lateralShare',
          'backwardShare', 'meanGain', 'meanFlight', 'throwingY', 'sidelineShare', 'xcp']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load():
    manifest = json.loads((EXPORT / 'manifest.json').read_text())
    hashes = {k: digest(EXPORT / f'{k}.csv') for k in ['throws', 'games', 'players', 'teams']}
    assert all(v == manifest['tables'][k]['sha256'] for k, v in hashes.items())
    games = pd.read_csv(EXPORT / 'games.csv', dtype=str, keep_default_na=False)
    players = pd.read_csv(EXPORT / 'players.csv', dtype=str, keep_default_na=False)
    teams = pd.read_csv(EXPORT / 'teams.csv', dtype=str, keep_default_na=False)
    assert not games.GameID.duplicated().any()
    assert players.groupby('PlayerID').full_name.nunique().max() == 1
    names = players.drop_duplicates('PlayerID').set_index('PlayerID').full_name.str.split().str.join(' ').to_dict()
    team_names = teams[teams.Year.eq('2026')].set_index('TeamID').FullName.to_dict()
    cols = ['GameID', 'throw_sig_id', 'Thrower', 'Receiver', 'ThrowerX', 'ThrowerY',
            'ReceiverX', 'ReceiverY', 'turnover', 'DroppedThrow', 'stall', 'cp', 'cpoe', 'aec',
            'source_event_type', 'possession_throw', 'game_quarter', 'quarter_point',
            'possession_num', 'is_home_team', 'global_event_seq']
    raw = pd.read_csv(EXPORT / 'throws.csv', usecols=cols, low_memory=False)
    assert not raw[['GameID', 'throw_sig_id']].duplicated().any()
    scope = games[games.Year.eq('2026') & games.RegularSeasonWeek.ne('') & games.PlayoffRound.eq('')]
    raw = raw.merge(scope[['GameID', 'StartTimestamp', 'HomeTeamID', 'AwayTeamID']],
                    on='GameID', how='inner', validate='many_to_one')
    raw['team'] = np.where(raw.is_home_team, raw.HomeTeamID, raw.AwayTeamID)
    raw['complete'] = raw.turnover.eq(0)
    raw['drop'] = raw.DroppedThrow.eq(1)
    raw['goal'] = raw.source_event_type.eq(19) & raw.complete
    raw['gain'] = raw.ReceiverY - raw.ThrowerY
    raw['dx'] = raw.ReceiverX - raw.ThrowerX
    raw['flight'] = np.hypot(raw.gain, raw.dx)
    finite = np.isfinite(raw[['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]).all(axis=1)
    bounds = (raw.ThrowerX.abs().le(26.67000001) & raw.ReceiverX.abs().le(26.67000001)
              & raw.ThrowerY.between(0, 120) & raw.ReceiverY.between(0, 120))
    raw['located'] = finite & bounds
    raw['named'] = raw.Thrower.notna() & ~raw.Thrower.str.lower().isin(['unknown', '', 'null', 'none'])
    raw['forward'] = raw.gain.gt(raw.dx.abs())
    raw['backward'] = (-raw.gain).gt(raw.dx.abs())
    raw['lateral'] = ~(raw.forward | raw.backward)
    raw['huck'] = raw.gain.gt(30) & raw.flight.gt(40)
    raw['short'] = raw.flight.le(10)
    raw['sideline'] = raw.ThrowerX.abs().ge(15)
    raw['throwAec'] = raw.aec.where(~raw['drop'], 0)
    # Stored cpoe is 1.0 on drops. Do NOT average that field. The cached official
    # player-game aggregates instead credit drops as thrower successes, then
    # subtract mean available cp. Also retain a matched-denominator sensitivity.
    raw['throwerSuccess'] = (raw.complete | raw['drop']).astype(int)
    raw['adjustedResidual'] = raw.throwerSuccess - raw.cp
    assert raw.loc[raw.goal, 'ReceiverY'].ge(100).all()
    links, counts = {}, Counter()
    keycols = ['GameID', 'team', 'game_quarter', 'quarter_point', 'possession_num']
    indexed, sequences = defaultdict(list), Counter()
    for r in raw.to_dict('records'):
        context = tuple(r[c] for c in keycols)
        indexed[(*context, r['possession_throw'])].append(r)
        sequences[(*context, r['global_event_seq'])] += 1
    for r in raw.to_dict('records'):
        context = tuple(r[c] for c in keycols)
        n = r['possession_throw']
        if not np.isfinite(n) or n < 2 or n != int(n):
            continue
        prev, current = indexed.get((*context, n - 1), []), indexed.get((*context, n), [])
        if len(prev) != 1 or len(current) != 1:
            continue
        p = prev[0]
        if (p['complete'] and p['stall'] == 0 and p['Receiver'] == r['Thrower']
                and p['global_event_seq'] < r['global_event_seq']
                and sequences[(*context, p['global_event_seq'])] == 1
                and sequences[(*context, r['global_event_seq'])] == 1):
            links[r['throw_sig_id']] = p
            if r['goal']:
                counts[(r['GameID'], p['Thrower'])] += 1
    raw['hockeyAssists'] = 0
    for r in raw[raw.goal].to_dict('records'):
        p = links.get(r['throw_sig_id'])
        if p:
            raw.loc[raw.throw_sig_id.eq(p['throw_sig_id']), 'hockeyAssists'] += 1
    raw['linkedPrior'] = raw.throw_sig_id.isin(links)
    raw['incomingBackward'] = raw.throw_sig_id.map(lambda k: bool(links[k]['backward']) if k in links else False)
    qc = dict(sourceRegularThrows=len(raw), observedGames=int(raw.GameID.nunique()),
              scheduledRegularGames=len(scope), stalls=int(raw.stall.eq(1).sum()),
              unnamedNonstall=int((~raw.named & raw.stall.eq(0)).sum()),
              invalidGeometryNonstall=int((~raw.located & raw.stall.eq(0)).sum()),
              missingCpNonstall=int((raw.cp.isna() & raw.stall.eq(0)).sum()),
              goals=int(raw.goal.sum()), goalsWithVerifiedPrior=int((raw.goal & raw.linkedPrior).sum()),
              missingGames=scope.loc[~scope.GameID.isin(raw.GameID), 'GameID'].tolist())
    return raw, names, team_names, hashes, qc


def profile(d, incoming=None):
    a = d[d.stall.eq(0)]
    z = a[a.located]
    scored = a[a.cp.notna()]
    h = z[z.huck]
    n = len(a)
    out = dict(throws=n, games=int(d.GameID.nunique()), completions=int(a.complete.sum()),
               drops=int(a['drop'].sum()), stalls=int(d.stall.eq(1).sum()),
               completionRate=float(a.complete.mean()), xcp=float(scored.cp.mean()),
               sourceCpoe=float(a.throwerSuccess.mean()-scored.cp.mean()),
               matchedCpoe=float(scored.adjustedResidual.mean()), scoredPasses=len(scored),
               meanGain=float(z.gain.mean()), meanFlight=float(z.flight.mean()), throwingY=float(z.ThrowerY.mean()),
               shortShare=float(z.short.mean()), huckShare=float(z.huck.mean()),
               forwardShare=float(z.forward.mean()), lateralShare=float(z.lateral.mean()),
               backwardShare=float(z.backward.mean()), sidelineShare=float(z.sideline.mean()),
               huckAttempts=len(h), huckCompletions=int(h.complete.sum()), huckDrops=int(h['drop'].sum()),
               assists=int(a.goal.sum()), hockeyAssists=int(a.hockeyAssists.sum()),
               throwerAec=float(d.throwAec.sum()), missingAec=int(d.aec.isna().sum()),
               linkedNextThrows=int(a.linkedPrior.sum()), incomingBackwardCount=int(a.incomingBackward.sum()),
               incomingBackwardShare=float(a.loc[a.linkedPrior, 'incomingBackward'].mean()),
               firstGame=str(d.StartTimestamp.min())[:10], lastGame=str(d.StartTimestamp.max())[:10])
    nonhucks = z[~z.huck]
    out.update(nonHuckThrows=len(nonhucks), nonHuckMeanGain=float(nonhucks.gain.mean()),
               nonHuckForwardShare=float(nonhucks.forward.mean()),
               nonHuckShortShare=float(nonhucks.short.mean()))
    if incoming is not None:
        c = incoming[incoming.complete & incoming.stall.eq(0) & incoming.located]
        out.update(catches=len(c), catchingY=float(c.ReceiverY.mean()),
                   incomingCatchBackwardShare=float(c.backward.mean()),
                   incomingCatchLateralShare=float(c.lateral.mean()),
                   incomingCatchForwardShare=float(c.forward.mean()),
                   catchesBehindThrowerShare=float(c.gain.lt(0).mean()))
    assert abs(out['forwardShare'] + out['lateralShare'] + out['backwardShare'] - 1) < 1e-10
    return out


def validate_cached(raw):
    """Bounded independent reconciliation to preserved official player-game rows."""
    checks, mismatch, seen = Counter(), [], set()
    grouped = {(g, p): d for (g, p), d in raw.groupby(['GameID', 'Thrower'])}
    for path in sorted((ROOT / 'data/source-api').glob('*.json')):
        obj = json.loads(path.read_text())
        if not isinstance(obj, dict) or not obj.get('game') or not obj.get('playerStats'):
            continue
        gid = obj['game']['GameID']
        if gid in seen or gid not in set(raw.GameID):
            continue
        seen.add(gid)
        for stat in obj['playerStats']:
            d = grouped.get((gid, stat['PlayerID']))
            if d is None:
                continue
            p = profile(d)
            for key, theirs in [('assists', 'Assists'), ('hockeyAssists', 'HockeyAssists'),
                                 ('xcp', 'xcp'), ('sourceCpoe', 'cpoe'), ('throwerAec', 'thrower_aec')]:
                if stat.get(theirs) is None:
                    continue
                checks[key] += 1
                if abs(p[key] - stat[theirs]) > 1e-8:
                    mismatch.append(dict(game=gid, player=stat['PlayerID'], metric=key,
                                         computed=p[key], source=stat[theirs]))
    return dict(games=len(seen), checked=dict(checks), mismatches=mismatch)


def run():
    raw, names, team_names, hashes, qc = load()
    rows, halves = [], []
    eligible_ids = []
    for pid, d in raw[raw.named].groupby('Thrower'):
        if d.team.nunique() != 1 or len(d[d.stall.eq(0)]) < 100 or d.GameID.nunique() < 6:
            continue
        eligible_ids.append(pid)
        p = profile(d, raw[raw.Receiver.eq(pid)])
        p.update(id=pid, name=names[pid], team=team_names[d.team.iloc[0]])
        early = d[['GameID', 'StartTimestamp']].drop_duplicates().sort_values('StartTimestamp').GameID.tolist()
        a, b = d[d.GameID.isin(early[:len(early)//2])], d[d.GameID.isin(early[len(early)//2:])]
        pa, pb = profile(a), profile(b)
        p['halves'] = dict(early=pa, later=pb)
        if min(pa['throws'], pb['throws']) >= 50:
            halves.append(p)
        rows.append(p)
    df = pd.DataFrame([{k:v for k,v in r.items() if k!='halves'} for r in rows])
    for p in rows:
        p['percentiles'] = {k:float(((df[k]<p[k]).sum() + .5*(df[k]==p[k]).sum())/len(df)*100) for k in TRAITS}
    early = pd.DataFrame([r['halves']['early'] for r in halves])
    later = pd.DataFrame([r['halves']['later'] for r in halves])
    stability = [dict(trait=k, spearman=float(early[k].rank().corr(later[k].rank())),
                      medianAbsoluteChange=float((early[k]-later[k]).abs().median())) for k in TRAITS]
    validation = validate_cached(raw)
    # Independently count the six examples from csv.DictReader, without pandas joins.
    game_ids = set(raw.GameID)
    counts = Counter()
    gains = defaultdict(list)
    nonhuck_gains = defaultdict(list)
    with (EXPORT / 'throws.csv').open() as f:
        for r in csv.DictReader(f):
            if r['GameID'] in game_ids and r['Thrower'] in EXAMPLES and float(r['stall'])==0:
                counts[r['Thrower']] += 1
                dy = float(r['ReceiverY']) - float(r['ThrowerY'])
                dx = float(r['ReceiverX']) - float(r['ThrowerX'])
                gains[r['Thrower']].append(dy)
                if not (dy > 30 and math.hypot(dx, dy) > 40):
                    nonhuck_gains[r['Thrower']].append(dy)
    examples = [next(r for r in rows if r['id']==pid) for pid in EXAMPLES]
    assert all(counts[r['id']]==r['throws'] for r in examples)
    for r in examples:
        assert abs(math.fsum(gains[r['id']])/len(gains[r['id']])-r['meanGain']) < 1e-10
        assert abs(math.fsum(nonhuck_gains[r['id']])/len(nonhuck_gains[r['id']])-r['nonHuckMeanGain']) < 1e-10
        assert r['scoredPasses'] == r['throws']
    assert all(m['metric']=='hockeyAssists' for m in validation['mismatches']), validation['mismatches']
    article_date = [dict(id=pid, **profile(raw[raw.Thrower.eq(pid) & raw.StartTimestamp.lt('2026-06-23')])) for pid in EXAMPLES]
    result = dict(question='Can all-pass throwing profiles support descriptions like the UFA six-passer article?',
        analyzedAt=datetime.now(timezone.utc).isoformat(), sourceSnapshot='2026-10-12', article=ARTICLE,
        sourceHashes=hashes, scope='2026 regular season, all lines, named throwers; physical passes exclude stalls.',
        cohort=dict(players=len(rows), minimumThrows=100, minimumGames=6, singleTeam=True, minimumCatches=None),
        quality=qc, cachedAggregateValidation=validation, independentExampleCounts=dict(counts),
        independentChartChecks='All six example pass counts, mean gains and non-huck mean gains independently recomputed with csv.DictReader and math.fsum; match within 1e-10. All six have complete cp coverage.',
        leaguePooled=profile(raw[raw.named], raw), qualifiedMedian={k:float(df[k].median()) for k in TRAITS},
        examples=examples, allProfiles=rows, articleDateComparison=article_date,
        repeatability=dict(players=len(halves), features=stability,
            method='Per-player chronological first half of observed games vs remaining games; >=50 non-stall throws per half. Exploratory same-season rank correlation, not a future-season validation.'),
        definitions=dict(xcp='Mean supplied cp over non-stall passes with non-missing cp.',
            sourceCpoe='(Completed passes + recorded drops) / all non-stall passes minus mean available cp, matching cached player-game aggregate convention. Drops receive thrower success credit. Expected completion excludes missing cp; matchedCpoe retains a sensitivity using only scored passes in both terms. All six examples have complete cp coverage. The stored per-pass cpoe field equals 1 on drops and is not averaged.',
            completionRate='Actual completions / all non-stall passes, including drops as incompletions.',
            huck='Forward gain >30 yards AND Euclidean flight >40 yards, strictly.',
            directions='Forward: gain > abs(lateral displacement). Backward: -gain > abs(lateral displacement). Lateral: remainder. Exact 45-degree boundaries are lateral. Disc direction does not identify a cutting route or forehand/backhand.',
            hockeyAssists='Completed immediately preceding pass before a source goal (event type 19), verified unique consecutive possession_throw, same game/team/quarter/point/possession, receiver=next thrower, increasing unique global_event_seq.',
            throwerAec='Sum supplied aec including stalls, with drops credited zero to thrower; source model, no division by attempts.',
            percentile='Midrank among eligible throwers, descriptive style position, not quality.'),
        caveats=['One regular-season game (Pittsburgh at Chicago) has no exported throws; both teams have incomplete coverage.',
            'The article was published June 23. Our main comparison uses all exported 2026 regular-season games, not its historical snapshot.',
            'These are descriptive dimensions and candidate role interpretations, not validated discrete archetypes.',
            'xCP/CPOE are supplied-model assessments; current exports may include revised model values. No independent calibration or future-year skill validation is claimed.',
            'Lag contribution and on-field possession denominators are not columns in the five exports. Cached aggregate samples do not supply complete comparable season coverage, so LC and per-100-possession claims are not reproduced.',
            'No receiver route, defender position, wind, mark, intent, vision, or causal effect on a lineup is inferred.',
            'CPOE credit treats drops differently from actual completion; the two cannot be subtracted interchangeably.',
            'Verified pre-assist counts are derived from unambiguous event links; they differ from cached official HockeyAssists in 21 of 991 checked player-games. These are not presented as exact official hockey-assist totals.',
            'There are 18 non-stall passes without cp. Official-style CPOE and an alternative using matched modeled-pass denominators differ for those players; all six article examples have complete modeled-pass coverage.'])
    path=Path(__file__).with_suffix('.json')
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['cohort','quality','cachedAggregateValidation','qualifiedMedian','repeatability']},indent=2))
    print(pd.DataFrame(examples)[['name','throws','games','completionRate','xcp','sourceCpoe','forwardShare','lateralShare','shortShare','huckShare','throwingY','assists','hockeyAssists','incomingCatchBackwardShare','throwerAec']].to_string(index=False))


if __name__ == '__main__':
    run()
