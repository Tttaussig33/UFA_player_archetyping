"""Requested playoff-team view and point outcomes after receiving-team turnovers.

This extends the preserved Nov 5 analysis without refitting its original models.
Breaks are opponent goals in the same point, not simply failed possessions.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import analyze

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OFFICIAL={'windchill','radicals','alleycats','glory','empire','breeze',
          'sol','flyers','growlers','spiders','cascades','shred'}

def main():
    analyze.RNG=np.random.default_rng(20261106)
    base=json.loads((ROOT/'results.json').read_text())
    for name,digest in base['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    allp=pd.read_csv(ROOT/'possessions.csv')
    p=allp[~allp.has_timeout].copy()
    games_path=REPO/'data/database-exports/2026-10-12/games.csv'
    games=pd.read_csv(games_path)
    playoffs=games[games.Year.eq(2026)&games.PlayoffRound.notna()&games.is_final]
    ids=set(playoffs.HomeTeamID)|set(playoffs.AwayTeamID)
    assert ids==OFFICIAL and len(ids)==12 and len(playoffs)==11
    # A regain counts even if that later possession was excluded for a timeout.
    # Use the unfiltered sequence so exclusions cannot erase an actual recovery.
    last_number=allp.groupby('point_id').own_possession.max()
    turnovers=p[p.outcome.eq('turnover')].copy()
    turnovers['regain_again']=turnovers.point_id.map(last_number).gt(turnovers.own_possession).astype(int)
    turnovers['eventual_break']=(turnovers.point_end.eq('goal')&turnovers.point_hold.eq(0)).astype(int)
    turnovers['break_before_regain']=(turnovers.eventual_break.eq(1)&turnovers.regain_again.eq(0)).astype(int)
    turnovers['regain_then_break']=(turnovers.eventual_break.eq(1)&turnovers.regain_again.eq(1)).astype(int)
    turnovers['eventual_hold']=(turnovers.point_end.eq('goal')&turnovers.point_hold.eq(1)).astype(int)
    resolved=turnovers[turnovers.point_end.eq('goal')].copy()
    assert (resolved.break_before_regain+resolved.regain_then_break+resolved.eventual_hold).eq(1).all()
    assert resolved.loc[resolved.eventual_hold.eq(1),'regain_again'].eq(1).all()
    result={
      'date':'2026-11-06',
      'scope':'Regular-season tendencies of all teams, with a view limited to the 12 teams that qualified for the 2026 playoffs. Playoff games identify membership only; they are not added to the tendency sample.',
      'playoff_source':{'url':'https://watchufa.com/league/news/2026-ufa-playoff-teams',
        'title':'12 Playoff Teams Are Set For 2026','published':'2026-07-13','accessed':'2026-11-06',
        'verification':'Exact team-ID set agrees with all 11 finalized 2026 playoff games in the preserved export.'},
      'playoff_team_ids':sorted(ids),'playoff_teams':[],
      'break_definition':'Among receiving-team possessions that end in a turnover, an eventual break means the opponent ultimately scores before that same point ends. Points ending with the period are listed separately and excluded from the resolved-point rate.',
      'break_filter':'Exclude the turnover possession if it contains a timeout. Later recoveries and point outcomes are followed through even if a timeout occurs later. Excluding every point with a timeout is a separate sensitivity.',
      'break_unit':'One receiving-team turnover. A point with multiple turnovers can contribute to multiple possession stages; uncertainty resamples whole games.',
      'break_adjustment':'Observed associations only. No new break model or playoff-only significance search. Turnover location, opponent strength and game situation may differ.',
      'break_league':analyze.observed(resolved,'eventual_break'),
      'break_before_regain_league':analyze.observed(resolved,'break_before_regain'),
      'break_teams':[],
      'break_outcome_counts':[],
      'playoff_summary':[]}
    result['break_league']['first_vs_all_subsequent']=analyze.observed(resolved,'eventual_break',(0,1),'regained')
    for s,q in turnovers.groupby('stage'):
        ended=q[q.point_end.eq('goal')]
        result['break_outcome_counts'].append({'stage':int(s),'turnovers':len(q),'resolved_points':len(ended),
          'period_ending_points':int(q.point_end.eq('period_end').sum()),
          'break_before_regain':int(ended.break_before_regain.sum()),
          'regain_then_break':int(ended.regain_then_break.sum()),
          'eventual_hold':int(ended.eventual_hold.sum()),'regain_again':int(ended.regain_again.sum())})
    for team in base['teams']:
        tid=team['team'];q=resolved[resolved.team.eq(tid)]
        br=analyze.observed(q,'eventual_break')
        br['first_vs_all_subsequent']=analyze.observed(q,'eventual_break',(0,1),'regained')
        result['break_teams'].append({'team':tid,**br})
        if tid not in ids:continue
        result['playoff_teams'].append({'team':tid,'team_name':team['team_name']})
        row={'team':tid,'team_name':team['team_name'],'metrics':{}}
        for metric in ['throws_goal','throws_turnover','scoring','early_huck']:
            gs=team['metrics'][metric]['groups']
            total_n=sum(g['n'] for g in gs[1:]);total_y=sum(g['sum'] for g in gs[1:])
            row['metrics'][metric]={'first':gs[0]['estimate'],'first_n':gs[0]['n'],
              'subsequent':total_y/total_n if total_n else None,'subsequent_n':total_n}
        row['metrics']['break_after_turnover']={'first':br['groups'][0]['estimate'],
          'first_n':br['groups'][0]['n'],
          'subsequent':br['first_vs_all_subsequent']['groups'][1]['estimate'],
          'subsequent_n':br['first_vs_all_subsequent']['groups'][1]['n']}
        result['playoff_summary'].append(row)
    result['break_sensitivities']={
      'exclude_whole_timeout_points':analyze.observed(resolved[~resolved.point_has_timeout],'eventual_break'),
      'include_period_ending_points_as_no_break':analyze.observed(turnovers,'eventual_break')}
    result['scoring_denominators']=base['league']['scoring']
    result['validation']={'passed':True,'checks':[
      'Nov 5 input hashes unchanged.','Playoff membership matches official UFA list and exported playoff games.',
      'For each resolved-point turnover, immediate break + regain then break + eventual hold = 1.',
      'Every eventual hold after a turnover includes a subsequent recorded regain.',
      'Timeout filtering does not remove later recovery events from the point-outcome classification.'],
      'method':'Descriptive follow-up with 10,000 whole-game bootstrap samples; seed 20261106.'}
    result['inputs']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['results.json','possessions.csv']}
    result['inputs']['games.csv']=hashlib.sha256(games_path.read_bytes()).hexdigest()
    analyze.dump('follow_up_20261106.json',result)
    print(json.dumps(analyze.clean({'break_league':result['break_league'],
       'playoff_summary':result['playoff_summary']}),indent=2))

if __name__=='__main__':main()
