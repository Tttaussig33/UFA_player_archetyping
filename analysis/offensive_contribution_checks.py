"""Independent CSV/scalar checks of all contribution rows and temporal splits."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
EXPORT=ROOT/'data/database-exports/2026-10-12'
RESULT=ROOT/'analysis/offensive_contributions.json'


def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):
        return None


def fresh():
    return dict(n=0,complete=0,drops=0,goals=0,cp=[],aec=[],gain=[],hucks=0,games=set())


def close(a,b,label):
    if a is None or b is None:
        assert a is b,(label,a,b)
    else:
        assert math.isclose(a,b,abs_tol=1e-9,rel_tol=1e-10),(label,a,b)


def ranks(values):
    ordered=sorted(enumerate(values),key=lambda v:v[1])
    ranked=[0.]*len(values)
    i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][1]==ordered[i][1]:j+=1
        for index,_ in ordered[i:j]:ranked[index]=(i+j-1)/2+1
        i=j
    return ranked


def spearman(a,b):
    x,y=ranks(a),ranks(b)
    xm,ym=math.fsum(x)/len(x),math.fsum(y)/len(y)
    numerator=math.fsum((a-xm)*(b-ym) for a,b in zip(x,y))
    denominator=math.sqrt(math.fsum((a-xm)**2 for a in x)*math.fsum((b-ym)**2 for b in y))
    return numerator/denominator if denominator else None


def run():
    result=json.loads(RESULT.read_text())
    with (EXPORT/'games.csv').open() as f:
        games={r['GameID']:r for r in csv.DictReader(f) if r['Year']=='2026' and r['RegularSeasonWeek'] and not r['PlayoffRound']}
    player_games=defaultdict(set); player_teams=defaultdict(set); totals=defaultdict(int)
    group=defaultdict(fresh); by_game=defaultdict(fresh)
    with (EXPORT/'throws.csv').open() as f:
        for r in csv.DictReader(f):
            gid,pid=r['GameID'],r['Thrower'].strip()
            if gid not in games or pid.lower() in ('','none','null','nan','unknown'):continue
            home=r['is_home_team'].lower() in ('true','t','1')
            player_games[pid].add(gid); player_teams[pid].add(games[gid]['HomeTeamID' if home else 'AwayTeamID'])
            if number(r['stall'])==1:continue
            totals[pid]+=1
            dx=number(r['ReceiverX'])-number(r['ThrowerX']); dy=number(r['ReceiverY'])-number(r['ThrowerY'])
            roles=['advance' if dy>abs(dx) else 'redistribute']
            if number(r['ReceiverY'])>=100:roles.append('score')
            complete=number(r['turnover'])==0; drop=number(r['DroppedThrow'])==1
            goal=complete and number(r['source_event_type'])==19
            cp,aec=number(r['cp']),number(r['aec'])
            for role in roles:
                for g in (group[pid,role],by_game[pid,role,gid]):
                    g['n']+=1; g['complete']+=complete; g['drops']+=drop; g['goals']+=goal
                    g['games'].add(gid)
                    g['hucks']+=dy>30 and math.hypot(dx,dy)>40
                    if cp is not None:g['cp'].append(cp)
                    if drop:g['aec'].append(0.)
                    elif aec is not None:g['aec'].append(aec)
                    if complete:g['gain'].append(dy)
    eligible={pid for pid,n in totals.items() if n>=100 and len(player_games[pid])>=6 and len(player_teams[pid])==1}
    assert eligible=={p['playerId'] for p in result['profiles']}
    for r in result['profiles']:
        pid,role=r['playerId'],r['role']; g=group[pid,role]; n=g['n']; cpn=len(g['cp'])
        assert r['attempts']==n and r['completions']==g['complete'] and r['drops']==g['drops'] and r['assists']==g['goals']
        assert r['totalPasses']==totals[pid] and r['games']==len(player_games[pid]) and r['roleGames']==len(g['games'])
        assert r['teamId'] in player_teams[pid] and r['scoredPasses']==cpn and r['hucks']==g['hucks']
        close(r['share'],n/totals[pid],r['id']+' share')
        close(r['completionRate'],g['complete']/n if n else None,r['id']+' completion')
        xcp=math.fsum(g['cp'])/cpn if cpn else None
        close(r['xcp'],xcp,r['id']+' xcp')
        close(r['cpoe'],(g['complete']+g['drops'])/n-xcp if n and cpn else None,r['id']+' cpoe')
        close(r['throwerAec'],math.fsum(g['aec']) if n else None,r['id']+' aec')
        close(r['meanCompletedGain'],math.fsum(g['gain'])/g['complete'] if g['complete'] else None,r['id']+' gain')
        assert (r['lowerPp'] is not None)==(n>=20 and len(g['games'])>=6 and cpn>0)
    for r in result['baselines']:
        gs=[group[pid,r['role']] for pid in eligible]
        assert r['attempts']==sum(g['n'] for g in gs)
        assert r['completions']==sum(g['complete'] for g in gs)
        assert r['assists']==sum(g['goals'] for g in gs)
        close(r['completionRate'],sum(g['complete'] for g in gs)/r['attempts'],'baseline completion')
        close(r['xcp'],math.fsum(v for g in gs for v in g['cp'])/sum(len(g['cp']) for g in gs),'baseline xcp')
    for r in result['halves']:
        pid,role=r['playerId'],r['role']
        assert set(r['earlyGames']).isdisjoint(r['laterGames'])
        assert set(r['earlyGames']+r['laterGames'])==player_games[pid]
        assert max(games[g]['StartTimestamp'] for g in r['earlyGames'])<min(games[g]['StartTimestamp'] for g in r['laterGames'])
        for half in ['early','later']:
            gs=[by_game[pid,role,gid] for gid in r[half+'Games']]
            n=sum(g['n'] for g in gs); complete=sum(g['complete'] for g in gs); drops=sum(g['drops'] for g in gs)
            cps=[v for g in gs for v in g['cp']]
            denominator=sum(by_game[pid,k,gid]['n'] for gid in r[half+'Games'] for k in ('advance','redistribute'))
            assert r[half]['attempts']==n and r[half]['totalPasses']==denominator
            close(r[half]['share'],n/denominator if denominator else None,'half share')
            close(r[half]['cpoe'],(complete+drops)/n-math.fsum(cps)/len(cps) if n and cps else None,'half cpoe')
    for s in result['repeatability']:
        pairs=s['passingPairs']
        close(s['shareSpearman'],spearman([p['earlyShare'] for p in pairs],[p['laterShare'] for p in pairs]),'frequency rho')
        measured=[p for p in pairs if min(p['earlyAttempts'],p['laterAttempts'])>=20 and p['earlyCpoe'] is not None and p['laterCpoe'] is not None]
        assert len(measured)==s['outcomePlayers']
        close(s['cpoeSpearman'],spearman([p['earlyCpoe'] for p in measured],[p['laterCpoe'] for p in measured]),'outcome rho')
    # Recompute one entire interval directly from independent game counters.
    first=result['profiles'][0]; split=result['halves'][0]; pid,role=first['playerId'],first['role']
    gs=[by_game[pid,role,gid] for gid in split['earlyGames']+split['laterGames']]
    matrix=np.array([[g['n'],g['complete'],g['drops'],len(g['cp']),math.fsum(g['cp'])] for g in gs])
    rng=np.random.default_rng(result['methods']['randomSeed'])
    resampled=matrix[rng.integers(0,len(gs),(2000,len(gs)))].sum(axis=1)
    residuals=100*((resampled[:,1]+resampled[:,2])/resampled[:,0]-resampled[:,4]/resampled[:,3])
    bounds=np.quantile(residuals,[.025,.975])
    close(first['lowerPp'],float(bounds[0]),'independent lower interval')
    close(first['upperPp'],float(bounds[1]),'independent upper interval')
    audit=dict(checkedAt=datetime.now(timezone.utc).isoformat(),resultSha256=hashlib.sha256(RESULT.read_bytes()).hexdigest(),
               eligiblePlayers=len(eligible),playerRoleRows=len(result['profiles']),halfRoleRows=2*len(result['halves']),
               baselines=len(result['baselines']),intervalsRecomputed=1,passed=True)
    (ROOT/'analysis/offensive_contribution_checks.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))


if __name__=='__main__':run()
