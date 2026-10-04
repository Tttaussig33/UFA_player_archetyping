"""Rebuild the reviewed snapshot from the preserved possession-browser cache.

Standard-library only. Input rows remain in data/raw; source API supplements are
in data/source-api. No live network request is made by this transformation.
"""
from __future__ import annotations
import csv, json, math, hashlib, collections
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TEAM_NAMES = {
    'alleycats': ('Indianapolis AlleyCats','IND'), 'apex': ('Colorado Apex','COL'),
    'bighorns': ('Vegas Bighorns','LV'), 'breeze': ('DC Breeze','DC'),
    'cascades': ('Seattle Cascades','SEA'), 'empire': ('New York Empire','NY'),
    'flyers': ('Carolina Flyers','CAR'), 'glory': ('Boston Glory','BOS'),
    'growlers': ('San Diego Growlers','SD'), 'havoc': ('Houston Havoc','HTX'),
    'hustle': ('Atlanta Hustle','ATL'), 'phoenix': ('Philadelphia Phoenix','PHI'),
    'radicals': ('Madison Radicals','MAD'), 'royal': ('Montreal Royal','MTL'),
    'rush': ('Toronto Rush','TOR'), 'shred': ('Salt Lake Shred','SLC'),
    'sol': ('Austin Sol','ATX'), 'spiders': ('Oakland Spiders','OAK'),
    'steel': ('Oregon Steel','ORE'), 'thunderbirds': ('Pittsburgh Thunderbirds','PIT'),
    'union': ('Chicago Union','CHI'), 'windchill': ('Minnesota Wind Chill','MIN'),
}

def truth(v):
    return str(v).lower() in ('true','1','1.0')

def number(v):
    try:
        v=float(v)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError): return None

def credit(t):
    """Matches the supplied per-game thrower_aec / receiver_aec totals."""
    a=number(t.get('aec'))
    if a is None: return None, None
    if not truth(t.get('turnover')): return a, a
    if truth(t.get('DroppedThrow')): return 0., a
    return a, 0.

def load_json(path): return json.loads(path.read_text())

def build():
    source=ROOT/'data/source-api'
    schedule=load_json(source/'schedule.json')['games']
    players={p['PlayerID']:{'id':p['PlayerID'],'name':' '.join(p['full_name'].split()),
              'portraitUrl':p.get('headshot_url')} for p in load_json(source/'leaderboard.json')['data']}
    payloads={}
    for f in source.glob('*.json'):
        p=load_json(f)
        if isinstance(p,dict) and p.get('game'):
            payloads[p['game']['GameID']]=p
            for s in p.get('playerStats',[]):
                pid=s['PlayerID']
                players.setdefault(pid,{'id':pid,'name':' '.join(s['full_name'].split())})
                if p.get('headshotUrls',{}).get(pid):players[pid]['portraitUrl']=p['headshotUrls'][pid]
    events=[]; games=[]; calls=[]; seen=set(); missing=[]; manifests=[]; validation=[]
    for game in sorted(schedule,key=lambda g:g['GameID']):
        gid=game['GameID']; phase='Regular season' if game.get('RegularSeasonWeek') is not None and not game.get('PlayoffRound') else 'Playoffs'
        cached=ROOT/'data/raw'/f'{gid}.csv'
        payload=payloads.get(gid)
        if payload and payload.get('throws'):
            rows=payload['throws']; origin=f'data/source-api/{gid}.json'
            if not (ROOT/origin).exists():origin='data/source-api/sample-game.json'
        elif cached.exists():
            with cached.open() as h:rows=list(csv.DictReader(h))
            origin=f'data/raw/{gid}.csv'
        else:rows=[];origin=f'data/source-api/{gid}.json'
        games.append({'game':gid,'date':gid[:10],'phase':phase,'home':game['HomeTeamID'],'away':game['AwayTeamID'],
                      'throws':len(rows),'status':game.get('Status'),'homeScore':game.get('HomeScore'),'awayScore':game.get('AwayScore')})
        if not rows:
            missing.append({'game':gid,'phase':phase,'reason':'The public API returned zero throws.'})
            continue
        f=ROOT/origin
        manifests.append({'file':origin,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'rows':len(rows)})
        sums=collections.defaultdict(lambda:[0.,0.])
        for i,t in enumerate(rows):
            key=f"{gid}:{t.get('throw_sig_id') or t.get('event_sig_id') or i}"
            assert key not in seen, f'Duplicate throw: {key}'
            seen.add(key)
            team=game['HomeTeamID'] if truth(t['is_home_team']) else game['AwayTeamID']
            ta,ra=credit(t)
            if ta is not None:sums[t['Thrower']][0]+=ta
            if t.get('Receiver') and ra is not None:sums[t['Receiver']][1]+=ra
            events.append({'id':key,'game':gid,'date':gid[:10],'phase':phase,'team':team,
                'thrower':t['Thrower'],'receiver':t.get('Receiver') or None,
                'tx':number(t['ThrowerX']),'ty':number(t['ThrowerY']),'rx':number(t['ReceiverX']),'ry':number(t['ReceiverY']),
                'complete':not truth(t['turnover']),'drop':truth(t['DroppedThrow']),'stall':truth(t['stall']),
                'aec':number(t.get('aec')),'throwAec':ta,'receiveAec':ra,'callahan':truth(t.get('is_callahan')),
                'line':'O-line' if truth(t.get('o_line')) else 'D-line','quarter':int(float(t['game_quarter']))})
        if payload and payload.get('throws'):
            for s in payload.get('playerStats',[]):
                for j,k in enumerate(('thrower_aec','receiver_aec')):
                    expected=number(s.get(k))
                    if expected is not None:
                        delta=sums[s['PlayerID']][j]-expected
                        validation.append({'game':gid,'player':s['PlayerID'],'metric':k,'delta':delta})
            # Match a Callahan defender only to a unique opposite-side throw in
            # the same game, quarter and point. No fuzzy nearest-event matching.
            ct=[t for t in rows if truth(t.get('is_callahan'))]
            for b in payload.get('blocks',[]):
                if not truth(b.get('is_callahan')):continue
                matches=[t for t in ct if int(t['game_quarter'])==int(b['game_quarter']) and
                         int(t['quarter_point'])==int(b['quarter_point']) and
                         truth(t['is_home_team'])!=truth(b['is_home_team'])]
                assert len(matches)==1, f'Ambiguous Callahan: {gid} {b}'
                t=matches[0]; a=number(t.get('aec'))
                calls.append({'id':f"{gid}:block:{b['event_sig_id']}",'game':gid,'date':gid[:10],'phase':phase,
                    'team':game['HomeTeamID'] if truth(b['is_home_team']) else game['AwayTeamID'],
                    'player':b['Defender'],'tx':number(t['ThrowerX']),'ty':number(t['ThrowerY']),
                    'rx':number(t['ReceiverX']),'ry':number(t['ReceiverY']),'aec':-a if a is not None else None,
                    'line':'O-line' if truth(b.get('o_line')) else 'D-line','opponentThrower':t['Thrower']})
    # Keep source values, including 0.02-yard sideline rounding and null aEC.
    unknown=sorted({p for e in events for p in [e['thrower'],e['receiver']] if p and p not in players})
    for pid in unknown:players[pid]={'id':pid,'name':pid}
    teams=[]
    for tid,(name,abbrev) in TEAM_NAMES.items():
        reg=[g for g in games if g['phase']=='Regular season' and tid in (g['home'],g['away'])]
        teams.append({'id':tid,'name':name,'abbrev':abbrev,'games':sum(g['throws']>0 for g in reg),
                      'scheduled':len(reg),'missing':', '.join(g['game'] for g in reg if not g['throws'])})
    teams.sort(key=lambda t:t['name'])
    stats={'throwRows':len(events),'regularSeasonThrows':sum(e['phase']=='Regular season' for e in events),
        'gamesWithThrows':sum(g['throws']>0 for g in games),'regularSeasonGames':sum(g['phase']=='Regular season' and g['throws']>0 for g in games),
        'teams':len(teams),'players':len(players),'nullAec':sum(e['aec'] is None for e in events),
        'callahans':len(calls),'missingGames':missing,'unknownPlayerNames':unknown,
        'playerMetricChecks':len(validation),'maxPlayerMetricDelta':max(abs(x['delta']) for x in validation),
        'metricDisagreements':[x for x in validation if abs(x['delta'])>1e-8],
        'coordinateExtrema':{k:[min(e[k] for e in events),max(e[k] for e in events)] for k in ('tx','ty','rx','ry')}}
    (ROOT/'data/validation.json').write_text(json.dumps(stats,indent=2))
    (ROOT/'data/source-manifest.json').write_text(json.dumps(manifests,indent=2))
    (ROOT/'data/players.json').write_text(json.dumps(list(players.values()),indent=2))
    now=datetime.now(timezone.utc).isoformat()
    metadata={'label':'Shown Space · 2026 UFA play-by-play','url':'https://shownspace.com',
       'files':['data/raw/*.csv','data/source-api/*.json'],'executedAt':now,
       'filters':['2026 season; regular season is the default. Playoffs can be selected separately.'],
       'caveats':['131 of 132 listed regular-season games have throws; Pittsburgh at Chicago on July 18 has none.',
          'The reference is a July 10 snapshot. These results use later cached/API data; rankings can differ.',
          'Zone edges are reconstructed from the video: x = -15, 0, 15; y = 20, 40, 60, 80, 100, 110 yards.',
          'Coordinates are source-normalized toward y=120. Values within 0.02 yards of the sidelines are clamped for drawing only.',
          'Throws with missing aEC stay in counts and vectors but are excluded from aEC totals.',
          'Original preserves three attacking-end-zone receiving zones, eight main-field throwing zones, and a Callahan bottom panel. Original includes releases at y=100 in the main field and catches/drops at y=100 in the attacking end zone. The Thrower aEC and Receiver aEC views cover all 12 zones, including the own end zone (0 <= y < 20); their bands include the lower edge and exclude the upper edge, except y=120 is included. Those views can separately show Callahans in the bottom panel.'],
       'evidenceFlow':[{'title':'Prior possession browser','detail':'Imported the 2026 per-game throw CSV cache from frisbee-analytics/data/raw/shownspace_throws_2026_by_game. Preserved in data/raw.'},
          {'title':'Schedule and names','detail':'GET https://shownspace.com/api/games?year=2026&limit=500 and GET https://shownspace.com/api/leaderboard?season=2026 on September 29, 2026.'},
          {'title':'Supplemental game records','detail':'GET https://shownspace.com/api/games/{GameID} for missing games and games with Callahans. Full returned records and hashes are preserved.'},
          {'title':'Reference','detail':'https://www.instagram.com/p/Danlzl5SoUs/ — Kings of the Field; player boxes, eight throwing zones, three receiving zones, and one defensive Callahan panel.'}],
       'metricDefinitions':[{'label':'Field-zone assignment','definition':'Original preserves three attacking-end-zone receiving zones, eight main-field throwing zones, and a Callahan bottom panel. Original includes releases at y=100 in the main field and catches/drops at y=100 in the attacking end zone. The Thrower aEC and Receiver aEC views cover all 12 zones, including the own end zone (0 <= y < 20); their bands include the lower edge and exclude the upper edge, except y=120 is included. Those views can separately show Callahans in the bottom panel.'},
          {'label':'Thrower aEC','definition':'Sum the supplied aEC for completions and non-drop turnovers. A dropped throw contributes zero to the thrower.'},
          {'label':'Receiver aEC','definition':'Sum supplied aEC for completions and drops credited to the named receiver. Untargeted throwaways have no receiver credit.'},
          {'label':'Callahan aEC','definition':'Reconstruction of the reference panel: negate the opposing Callahan throw aEC and assign it to the uniquely matched defender. This is separate from offensive player totals.'},
          {'label':'Completion rate','definition':'Completed throws divided by all throws in the selected player and zone. For receiving: catches divided by catches plus recorded drops.'}]}
    old=load_json(ROOT/'src/data.json')
    snapshot={'id':old['id'],'surface':'dashboard','title':'UFA player archetyping','generatedAt':now,'status':'reviewed','buildStatus':'creating','filters':[
        {'id':'team','label':'Team','field':'team','defaultValue':'glory','queryIds':['events','callahans']},
        {'id':'phase','label':'Season phase','field':'phase','defaultValue':'Regular season','queryIds':['events','callahans','games']},
        {'id':'line','label':'Line','field':'line','defaultValue':'all','queryIds':['events','callahans']}],
      'queries':{k:{'rows':rows,'source':dict(metadata),'methods':[{'language':'python','code':'python3 tools/build_dataset.py'}]} for k,rows in
        [('events',events),('callahans',calls),('players',list(players.values())),('teams',teams),('games',games)]}}
    (ROOT/'src/data.json').write_text(json.dumps(snapshot,separators=(',',':'),allow_nan=False))
    print(json.dumps(stats,indent=2))

if __name__=='__main__':build()
