"""Independent annual CSV reconciliation and numerical checks for the pilot.

CSV calculations below do not import the study's event/profile preparation.
Small numerical fixtures exercise the custom clustering and offset routines.
"""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from archetype_candidate_validation import adjusted_rand, silhouette, kmeans, fit_offsets

ROOT = Path(__file__).resolve().parents[1]


def check():
    result = json.loads((ROOT/'analysis/archetype_candidate_validation.json').read_text())
    folder = ROOT/'data/database-exports/2026-10-12'
    for table, expected in result['sourceHashes'].items():
        assert hashlib.sha256((folder/f'{table}.csv').read_bytes()).hexdigest() == expected
    with (folder/'games.csv').open() as file:
        games = {r['GameID']:r for r in csv.DictReader(file)}
    stats = defaultdict(lambda: dict(throws=0, catches=0, completions=0, short=0,
        huck=0, huckComplete=0, forward=0, backward=0, ty=0., ry=0., txside=0,
        rxside=0, throwGames=set(), catchGames=set(), gain=0.))
    missing = {'','unknown','none','null','nan'}
    with (folder/'throws.csv').open() as file:
        for row in csv.DictReader(file):
            g=games[row['GameID']]
            if g['Year']!='2026' or not g['RegularSeasonWeek'] or g['PlayoffRound'] or row['stall']=='1.0': continue
            try: tx,ty,rx,ry=(float(row[k]) for k in ['ThrowerX','ThrowerY','ReceiverX','ReceiverY'])
            except ValueError: continue
            if not(all(math.isfinite(v) for v in [tx,ty,rx,ry]) and abs(tx)<=26.67000001 and abs(rx)<=26.67000001 and 0<=ty<=120 and 0<=ry<=120): continue
            team=g['HomeTeamID'] if row['is_home_team']=='true' else g['AwayTeamID']
            complete=row['turnover']=='0.0'
            distance=math.hypot(rx-tx,ry-ty)
            if row['Thrower'].lower() not in missing:
                s=stats[(team,row['Thrower'])]
                s['throws']+=1; s['completions']+=complete; s['throwGames'].add(row['GameID'])
                s['short']+=distance<=10; s['huck']+=distance>40 and ry-ty>30
                s['huckComplete']+=distance>40 and ry-ty>30 and complete
                s['forward']+=ry-ty>abs(rx-tx); s['backward']+=ty-ry>abs(rx-tx)
                s['ty']+=ty; s['txside']+=abs(tx)>=15; s['gain']+=ry-ty
            if complete and row['Receiver'].lower() not in missing:
                s=stats[(team,row['Receiver'])]
                s['catches']+=1; s['catchGames'].add(row['GameID']); s['ry']+=ry; s['rxside']+=abs(rx)>=15
    teams=defaultdict(set)
    for t,p in stats: teams[p].add(t)
    independent={}
    for (t,p),s in stats.items():
        if len(teams[p])!=1 or min(s['throws'],s['catches'])<100 or min(len(s['throwGames']),len(s['catchGames']))<6: continue
        independent[p]=dict(team=t, throws=s['throws'],catches=s['catches'],completions=s['completions'],
            throwGames=len(s['throwGames']),catchGames=len(s['catchGames']),
            shortShare=s['short']/s['throws'],huckShare=s['huck']/s['throws'],forwardShare=s['forward']/s['throws'],
            backwardShare=s['backward']/s['throws'],releaseY=s['ty']/s['throws'],releaseSide=s['txside']/s['throws'],
            catchY=s['ry']/s['catches'],catchSide=s['rxside']/s['catches'],throwShare=s['throws']/(s['throws']+s['catches']),
            huckAttempts=s['huck'],huckCompletions=s['huckComplete'],meanForwardGain=s['gain']/s['throws'])
    assert len(independent)==len(result['profiles'])==230
    for p in result['profiles']:
        for field,value in independent[p['id']].items():
            assert value==p[field] if isinstance(value,str) else math.isclose(value,p[field],abs_tol=1e-10), (p['id'],field)
        assert math.isclose(p['completionRate']-p['expectedCompletion'],p['completionAboveExpected'],abs_tol=1e-12)
        assert p['completionLower']<=p['completionAboveExpected']<=p['completionUpper']
    assert adjusted_rand([0,0,1,1],[2,2,3,3])==1
    assert math.isclose(adjusted_rand([0,0,1,1],[0,1,0,1]),-.5)
    x=np.array([[0.],[1.],[10.],[11.]])
    expected=np.mean([(10.5-1)/10.5,(9.5-1)/9.5,(9.5-1)/9.5,(10.5-1)/10.5])
    assert math.isclose(silhouette(x,np.array([0,0,1,1])),expected)
    _,labels,inertia=kmeans(x,2,123)
    assert adjusted_rand(labels,[0,0,1,1])==1 and math.isclose(inertia,1)
    frame=pd.DataFrame({'player':['a']*8+['b']*8,'complete':[1]*6+[0]*2+[1]*2+[0]*6})
    offsets=fit_offsets(frame,np.full(16,.5),'player')
    assert math.isclose(offsets['a'],-offsets['b'])
    for key,beta in offsets.items():
        y=frame[frame.player.eq(key)].complete
        assert abs((y-1/(1+math.exp(-beta))).sum()-5*beta)<1e-8
    for study in result['clusterStudies']:
        assert study['referenceSeason']<study['testSeason']
        memberships=study['temporalMembership']
        assert math.isclose(adjusted_rand([r['earlyGroup'] for r in memberships],[r['laterGroup'] for r in memberships]),study['heldoutARI'])
        assert math.isclose(sum(study['weights'].values()),1.)
        assert study['passedPilotGates']==all(study['pilotGates'].values())
    for study in result['outcomeStudies']:
        assert max(study['geometryTrainingSeasons'])<study['testSeason']
        assert study['offsetTrainingSeason']==study['testSeason']-1
        assert study['convergence']['maxParameterChange']<1e-5
        c=study['comparisons']
        assert math.isclose(c['baselineBrier']-c['playerBrier'],c['absoluteBrierImprovement'],abs_tol=1e-14)
        assert c['gameBootstrap']['ci95'][0]<0<c['gameBootstrap']['ci95'][1]
    print('PASS: four source hashes; all 230 annual profiles independently reconciled; clustering/offset numerical fixtures; temporal membership, model dates and Brier arithmetic.')


if __name__=='__main__': check()
