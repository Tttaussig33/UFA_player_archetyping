"""Compare throwing contributions and observed outcomes across the 2026 cohort.

Read-only analysis of preserved CSVs. Contributions are queries on passes, not
mutually exclusive player archetypes. No intrinsic skill or lineup effect model.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import math

import numpy as np
import pandas as pd
from thrower_article_comparison import load

ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    'advance': 'Advancement',
    'redistribute': 'Redistribution',
    'score': 'Scoring delivery',
}
BOOTSTRAPS = 2000
SEED = 20261030


def describe_role(passes, mask, total_passes, all_games, rng=None):
    selected = passes[mask]
    n = len(selected)
    scored = selected[selected.cp.notna()]
    completed = int(selected.complete.sum())
    drops = int(selected['drop'].sum())
    expected_sum = float(scored.cp.sum())
    cp_n = len(scored)
    cpoe = (completed + drops) / n - expected_sum / cp_n if n and cp_n else None
    result = dict(attempts=n, completions=completed, drops=drops,
                  roleGames=int(selected.GameID.nunique()), totalPasses=total_passes,
                  share=n/total_passes if total_passes else None,
                  completionRate=completed/n if n else None,
                  xcp=expected_sum/cp_n if cp_n else None,
                  scoredPasses=cp_n, expectedCompletions=expected_sum,
                  cpoe=cpoe, cpoePp=cpoe*100 if cpoe is not None else None,
                  assists=int(selected.goal.sum()),
                  throwerAec=float(selected.throwAec.sum()) if n else None,
                  missingAec=int(selected.aec.isna().sum()),
                  completedGain=float(selected.loc[selected.complete, 'gain'].sum()),
                  meanCompletedGain=float(selected.loc[selected.complete, 'gain'].mean()) if completed else None,
                  meanAttemptGain=float(selected.gain.mean()) if n else None,
                  hucks=int(selected.huck.sum()),
                  firstGame=min(all_games) if all_games else None,
                  lowerPp=None, upperPp=None, bootstrapGames=len(all_games))
    # Resample all of the player's observed games, including zero-role games.
    # Minimum counts govern interval display only, never eligibility in the cohort.
    if rng is not None and n >= 20 and result['roleGames'] >= 6 and cp_n:
        g = selected.assign(scored=selected.cp.notna()).groupby('GameID').agg(
            attempts=('complete', 'size'), completions=('complete', 'sum'),
            drops=('drop', 'sum'), scored=('scored', 'sum'), cp=('cp', 'sum'))
        g = g.reindex(all_games, fill_value=0).to_numpy(float)
        totals = g[rng.integers(0, len(g), (BOOTSTRAPS, len(g)))].sum(axis=1)
        valid = (totals[:, 0] > 0) & (totals[:, 3] > 0)
        vals = ((totals[valid, 1]+totals[valid, 2])/totals[valid, 0]-totals[valid, 4]/totals[valid, 3])*100
        if len(vals) >= BOOTSTRAPS*.95:
            result['lowerPp'], result['upperPp'] = [float(v) for v in np.quantile(vals, [.025, .975])]
    return result


def masks(passes):
    # Direction definitions match the existing all-pass profiles. A target on
    # the goal line is kept regardless of outcome; it is not assumed to score.
    return {'advance': passes.forward, 'redistribute': ~passes.forward,
            'score': passes.ReceiverY.ge(100)}


def rank_correlation(rows, left, right):
    if len(rows) < 3:
        return None
    a = pd.Series([r[left] for r in rows], dtype=float)
    b = pd.Series([r[right] for r in rows], dtype=float)
    if not a.nunique() > 1 or not b.nunique() > 1:
        return None
    return float(a.rank(method='average').corr(b.rank(method='average')))


def run():
    raw, names, teams, hashes, quality = load()
    prior = json.loads((ROOT/'analysis/thrower_article_comparison.json').read_text())
    assert hashes == prior['sourceHashes']
    cohort_ids = {p['id'] for p in prior['allProfiles']}
    eligible = raw[raw.Thrower.isin(cohort_ids)]
    passes = eligible[eligible.stall.eq(0)]
    assert passes.located.all()
    rng = np.random.default_rng(SEED)
    profiles, halves = [], []
    for pid, events in eligible.groupby('Thrower', sort=True):
        a = events[events.stall.eq(0)]
        games = events[['GameID', 'StartTimestamp']].drop_duplicates().sort_values(['StartTimestamp','GameID']).GameID.tolist()
        early_games, later_games = games[:len(games)//2], games[len(games)//2:]
        assert set(early_games).isdisjoint(later_games)
        for role, mask in masks(a).items():
            record = describe_role(a, mask, len(a), games, rng)
            record.update(id=f'{pid}:{role}', playerId=pid, name=names[pid], teamId=events.team.iloc[0],
                          teamName=teams[events.team.iloc[0]], role=role, roleName=ROLES[role], games=len(games))
            profiles.append(record)
            split = {}
            for half, game_ids in [('early', early_games), ('later', later_games)]:
                part = a[a.GameID.isin(game_ids)]
                split[half] = describe_role(part, masks(part)[role], len(part), game_ids)
            halves.append(dict(playerId=pid, name=names[pid], teamId=events.team.iloc[0], role=role,
                               earlyGames=early_games, laterGames=later_games, **split))
    baselines, study = [], []
    for role, mask in masks(passes).items():
        members = [p for p in profiles if p['role'] == role]
        totals = describe_role(passes, mask, len(passes), sorted(passes.GameID.unique()))
        shares = [p['share'] for p in members]
        totals.update(role=role, roleName=ROLES[role], players=len(members),
                      shareP25=float(np.quantile(shares,.25)), shareMedian=float(np.median(shares)),
                      shareP75=float(np.quantile(shares,.75)),
                      playersWith20=sum(p['attempts']>=20 for p in members),
                      playersWith50=sum(p['attempts']>=50 for p in members))
        baselines.append(totals)
        split_rows = []
        for h in halves:
            if h['role'] != role or min(h['early']['totalPasses'],h['later']['totalPasses']) < 50:
                continue
            split_rows.append(dict(playerId=h['playerId'], teamId=h['teamId'],
                                   earlyShare=h['early']['share'], laterShare=h['later']['share'],
                                   earlyAttempts=h['early']['attempts'], laterAttempts=h['later']['attempts'],
                                   earlyCpoe=h['early']['cpoe'], laterCpoe=h['later']['cpoe'],
                                   earlyCompletion=h['early']['completionRate'], laterCompletion=h['later']['completionRate']))
        outcomes = [s for s in split_rows if min(s['earlyAttempts'],s['laterAttempts'])>=20
                    and s['earlyCpoe'] is not None and s['laterCpoe'] is not None]
        study.append(dict(role=role, roleName=ROLES[role], sharePlayers=len(split_rows),
                          shareSpearman=rank_correlation(split_rows,'earlyShare','laterShare'),
                          shareMedianChangePp=float(np.median([abs(s['earlyShare']-s['laterShare'])*100 for s in split_rows])),
                          outcomePlayers=len(outcomes),
                          completionSpearman=rank_correlation(outcomes,'earlyCompletion','laterCompletion'),
                          cpoeSpearman=rank_correlation(outcomes,'earlyCpoe','laterCpoe'),
                          passingPairs=split_rows))
    assert len(profiles) == len(cohort_ids)*3
    assert sum(p['attempts'] for p in profiles if p['role']!='score') == len(passes)
    assert all(p['completions']<=p['attempts'] and p['assists']<=p['completions'] for p in profiles)
    scoring = passes.ReceiverY.ge(100)
    coverage = dict(quality, qualifiedPlayers=len(cohort_ids), qualifiedPasses=len(passes),
                    qualifiedGames=int(passes.GameID.nunique()),
                    scoringCompletionsNotGoals=int((scoring & passes.complete & ~passes.goal).sum()),
                    scoringGoals=int(passes.loc[scoring,'goal'].sum()),
                    scoringNonGoalOnLine=int((scoring & passes.complete & ~passes.goal & passes.ReceiverY.eq(100)).sum()))
    result = dict(question='How do UFA throwers advance, redistribute and deliver scoring passes, and how effective are they at each?',
                  analyzedAt=datetime.now(timezone.utc).isoformat(), sourceSnapshot='2026-10-12',
                  season=2026, sourceHashes=hashes, cohort=prior['cohort'], coverage=coverage,
                  profiles=profiles, baselines=baselines, repeatability=study, halves=halves,
                  methods=dict(bootstrapGames=BOOTSTRAPS, randomSeed=SEED,
                               intervalMinimumAttempts=20, intervalMinimumRoleGames=6,
                               halfMinimumTotalPasses=50, halfMinimumRoleAttemptsForOutcomes=20),
                  definitions=dict(
                      advance='Gain > abs(lateral displacement): forward-directed passes within 45 degrees of straight ahead. Gain = ReceiverY − ThrowerY; attack is toward Y=120.',
                      redistribute='All remaining physical passes: lateral or backward. Exact 45-degree boundaries are lateral. This is a directional proxy; it does not prove tactical intent or measure off-disc organization.',
                      score='Recorded target Y ≥100, including the goal line, regardless of completion. Includes hucks and short end-zone passes; may overlap either direction group. Assists are counted separately from source event type 19 plus complete=true. No attempt is classified by its outcome.',
                      share='Role attempts / all non-stall passes by the player. Advancement + redistribution =100%; scoring overlaps them and is not added.',
                      completion='Actual completed passes / role attempts. Recorded drops remain incomplete.',
                      cpoe='100 × ((completions + recorded drops)/attempts − mean supplied cp on available scored role passes). Drops receive thrower credit, matching the existing source-aggregate convention. Expected completion excludes missing cp. This is a retrospective supplied-model comparison, not intrinsic player skill.',
                      intervals='Pointwise 95% percentile intervals from 2,000 within-player whole-game bootstrap replicates, keeping zero-role games. Display only with ≥20 role attempts and ≥6 games containing the role. Conditional on the supplied cp model; not simultaneous best-player tests.',
                      totals='Role thrower aEC sums supplied throwAec for these physical passes, drops credited zero. Stalls do not have a pass direction and are excluded here. No aEC/attempt metric is used. Completed gain sums only completed pass Y changes; resets can have negative gain.',
                      repeatability='Per-player chronological first half of observed games versus remaining games. Shares use players with ≥50 total passes in each half; completion/CPOE additionally require ≥20 role attempts in each half. Spearman rank correlation measures same-season association, not future-season prediction. Team context and supplied-model fitting are not controlled.',
                      baseline='Pooled pass-weighted outcomes from the fixed cohort of 249 qualifying throwers. Quartiles describe equally weighted player shares. Neither baseline changes with team, search, or sample controls.'),
                  caveats=[
                      'October 12, 2026 export, regular season and all lines. Pittsburgh at Chicago on July 18 has no exported throws.',
                      'Advancement and redistribution are complementary directional categories; their frequency correlations are mechanically identical. They are not two independent discoveries.',
                      'Scoring-target completions on the goal line can be recorded as non-goals. Display actual source assists separately; do not equate target completions with goals.',
                      'Shares reflect opportunities and team roles. Low involvement, multiple-team seasons and fewer than six observed games are outside the fixed cohort.',
                      'No force direction, receiver routes, defensive positioning, wind, possession scoring probability or replacement effects are inferred.',
                      'Player rankings and intervals are exploratory and descriptive. No natural clusters or fixed archetype labels are fitted in this study.',
                      'Role CPOE uses supplied probabilities without an independent calibration check. Whole-game intervals cannot remove unmeasured context or model error.',
                  ])
    path=ROOT/'analysis/offensive_contributions.json'
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(coverage=coverage,baselines=baselines,
                          repeatability=[{k:v for k,v in r.items() if k!='passingPairs'} for r in study]),indent=2))


if __name__ == '__main__':
    run()
