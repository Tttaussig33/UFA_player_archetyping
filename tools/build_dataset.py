"""Rebuild the reviewed snapshot from preserved local inputs.

The selected database export is authoritative when current.json exists. Older
projects without an import continue to use their possession-browser cache.
Cached public API responses supply portrait URLs and historical metric checks.
No live network request is made by this transformation.
"""
from __future__ import annotations
import csv, json, math, hashlib, collections
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
from database_exports import load_bundle
from player_profiles import add_player_profiles
from thrower_profiles import add_thrower_profiles
from offensive_contributions import add_offensive_contributions

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

CONNECTION_DEFINITIONS = [
    {'label':'Passing connections','componentIds':['ufa-connections-chart','ufa-connection-records'],
     'definition':'For the selected player, count each eligible pass from a teammate on the incoming side and to a teammate on the outgoing side. The sides are separate event totals across the selected games, not a sequence within one possession. Stalls are excluded.'},
    {'label':'Huck passes','componentIds':['ufa-connections-chart','ufa-connection-records'],
     'definition':'A huck has recorded flight distance sqrt((rx-tx)^2 + (ry-ty)^2) > 40 yards and forward gain ry-ty > 30 yards. The source normalizes every offense toward y=120. Missing coordinates cannot qualify. Hucks only filters incoming and outgoing passes.'},
    {'label':'Connection outcomes','componentIds':['ufa-connections-chart','ufa-connection-records'],
     'definition':'Completed passes is the default. All pass attempts additionally includes drops and other incompletions, without discarding unnamed targets. Unrecorded player means the source did not name that endpoint; an intended receiver is never inferred.'},
    {'label':'Displayed partners','componentIds':['ufa-connections-chart'],
     'definition':'Rank each side independently by eligible pass count. Top 5 and Top 10 retain remaining partners in an additive Other players group. All partners shows every recorded partner. Source rows retain every original pass once, and a selected link retrieves only its corresponding passes.'},
]

def add_connection_metadata(snapshot):
    query=snapshot['queries']['events']
    source=query['source']
    labels={item['label'] for item in CONNECTION_DEFINITIONS}
    source['metricDefinitions']=[item for item in source.get('metricDefinitions',[]) if item.get('label') not in labels]+CONNECTION_DEFINITIONS
    method={'language':'text','code':'src/content/dashboard/connections-model.js: buildConnections filters reviewed events by selected player, pass outcome and huck geometry after team/phase/line filtering; it groups incoming and outgoing passes separately by partner, retaining all remaining partners in Other players. selectedConnectionEvents resolves selected diagram endpoints to original event IDs. No pass sequence is inferred.'}
    query['methods']=[item for item in query.get('methods',[]) if not item.get('code','').startswith('src/content/dashboard/connections-model.js:')]+[method]
    definition_flow={'title':'Huck definition clarified','detail':'On October 22, 2026 the user supplied strict cutoffs: receiver Y minus thrower Y >30 yards and Euclidean endpoint distance >40 yards, with attack normalized toward y=120. The local huck filters now share these rules. This changes derived classification only; the imported database rows are unchanged. The October 12, 2026 snapshot had no throws on either former inclusive boundary.'}
    source['evidenceFlow']=[item for item in source.get('evidenceFlow',[]) if item.get('title')!='Huck definition clarified']+[definition_flow]
    return snapshot

def add_radial_metadata(snapshot):
    query=snapshot['queries']['events']
    source=query['source']
    components=['ufa-radial-throw','ufa-radial-receive','ufa-radial-records']
    definitions=[
        {'label':'Radial direction buckets','componentIds':components,
         'definition':'Reproduce prod.get_player_throw_directions from its read-only October 12, 2026 definition: normalize supplied throwAngle modulo 360 and group by floor(angle / 30). Twelve buckets include their lower edge and exclude their upper edge. Missing angles are excluded, not reconstructed.'},
        {'label':'Radial counts and shares','componentIds':components,
         'definition':'Count thrower and receiver involvement separately. Each bucket share divides its count by the selected role’s total events with recorded angles, after the team, season phase, line, player, outcome and huck filters. The pass list deduplicates shared source events; role totals are not a possession total. An empty role has no percentage denominator.'},
        {'label':'Radial outcomes','componentIds':components,
         'definition':'All recorded (original) matches the function’s inclusion of incompletions, named targets and stalls. Completed passes keeps complete=true only. Receiving is the named Receiver endpoint, including unsuccessful targets when All recorded is selected. Unnamed targets are never inferred. The huck filter excludes stalls, as in Connections.'},
        {'label':'Radial display','componentIds':['ufa-radial-throw','ufa-radial-receive'],
         'definition':'Rendered Shown Space profile inspected October 14, 2026: 0 degrees at the top, clockwise; wedges centered on each bucket’s lower-edge angle; receiving angles are not rotated. Radius is innerRadius + (outerRadius-innerRadius) * bucketShare / scaleMaximum. Original scale uses each role’s maximum share; Shared percentage uses the maximum across both roles. Length, not wedge area, encodes frequency; outer-ring percentages disclose the scale.'},
    ]
    labels={item['label'] for item in definitions}
    source['metricDefinitions']=[item for item in source.get('metricDefinitions',[]) if item.get('label') not in labels]+definitions
    for definition in source['metricDefinitions']:
        if definition['label']=='Huck passes':
            definition['componentIds']=list(dict.fromkeys(definition['componentIds']+components))
    method={'language':'text','code':'src/content/dashboard/radial-model.js: buildRadials applies selected player, outcome and huck filters to the page-scoped events, excludes missing throwAngle, normalizes modulo 360 and counts each role in twelve lower-inclusive 30-degree buckets. radialRecords resolves selected role/bucket to original source events. Grouping is from data/database-metadata/2026-10-12/get_player_throw_directions.sql; comparison fixture is alex-atkins-2026-radial.json. Radials.jsx reproduces the inspected reference orientation and radial-length scaling, with an optional shared percentage scale.'}
    query['methods']=[item for item in query.get('methods',[]) if not item.get('code','').startswith('src/content/dashboard/radial-model.js:')]+[method]
    flow={'title':'Radial reference','detail':'The read-only prod.get_player_throw_directions definition and aatkins / 2026 / 12 result were captured October 12, 2026. Its counts reconcile to the imported local snapshot. The visible SVG on https://shownspace.com/players/aatkins was inspected October 14, 2026 to reproduce wedge positioning and radius scaling. The new local filters operate on the CSV snapshot; this is not a live database refresh.'}
    source['evidenceFlow']=[item for item in source.get('evidenceFlow',[]) if item.get('title')!='Radial reference']+[flow]
    return snapshot

def add_deep_thrower_metadata(snapshot):
    query=snapshot['queries']['events']
    source=query['source']
    components=['ufa-deep-profile','ufa-deep-receive','ufa-deep-release','ufa-deep-comparison','ufa-deep-sequences','ufa-deep-setups']
    definitions=[
        {'label':'Deep thrower performance','componentIds':components,
         'definition':'Hucks use the Connections definition: non-stall throws with endpoint flight >40 yards and forward gain >30 yards. Completion is completed hucks / all huck attempts, retaining drops and unnamed targets. Huck share is hucks / non-stall throws with all four finite endpoint coordinates; missing geometry is excluded from this denominator. Individual huck records and CSV exports retain the supplied thrower aEC.'},
        {'label':'Deep thrower field zones','componentIds':['ufa-deep-receive','ufa-deep-release','ufa-deep-profile'],
         'definition':'Use the same twelve exhaustive field zones as the full-field views, normalized toward y=120. Receiving counts completed catches at rx/ry; release performance uses hucks at tx/ty. Catch shares divide by all catches in the selected receiving view, including any unmapped catches. Out-of-field endpoints are excluded only from spatial cells, with counts disclosed. The zone minimum applies to performance shading, the highest-observed-zone summary and eligibility when ranking a particular release zone. Low-sample cells in otherwise eligible rows retain their counts. Profile source rows and exports retain every selected huck. Counts are never converted into area-normalized densities; zone sizes differ.'},
        {'label':'Verified pass before a huck','componentIds':['ufa-deep-receive','ufa-deep-sequences','ufa-deep-setups'],
         'definition':'Within the page-scoped events, match by game, team, quarter, point and possession. The prior pass has possessionThrow exactly one less than the huck; both order keys and event sequence keys must be unique within that context, and the prior eventSequence must be smaller. Require a completed, non-stall prior pass whose receiver is the huck thrower. Missing, first-throw and ambiguous cases remain unmatched, not inferred as dead-disc starts. The preceding catch is the prior pass destination, which may differ from the next recorded release. No receiver movement, upline, swing, defensive position or dead-disc label is inferred.'},
        {'label':'Deep thrower leaderboard','componentIds':['ufa-deep-comparison'],
         'definition':'One matrix row per named thrower, with completion rates and completed/attempted hucks by release zone. The player minimum uses all hucks in the team, phase and line scope. Ranking one zone additionally requires the zone minimum there. The completion filter applies to the ranked location: at least the scope baseline by default, or at least 70%, at least 80%, or any rate. All eligibility filters precede name/team search. Sort uses the chosen location and selected measure descending, then attempts, then completion rate, then player ID. Attempt sorting measures volume, not quality. The scope baseline pools all named throwers before sample minimums, completion filtering and search, summing numerators and denominators rather than averaging rates. Source rows include their non-stall throws to preserve huck-share denominators. Display rows contain the complete matching leaderboard plus scope baseline in player/zone long form; pagination shows fifteen players. Nine non-attacking-end-zone columns remain visible; attacking-end-zone columns are added if they have attempts or are the selected ranking zone. Unmapped releases remain in all-location totals. The fixed 0–100% color scale is identical across columns; below-minimum cells are hatched. These are observed outcomes, not difficulty-adjusted ratings or learned archetypes.'},
        {'label':'Release location comparisons','componentIds':['ufa-deep-comparison','ufa-deep-release','ufa-deep-profile'],
         'definition':'Compare a player’s completion rate in a release zone with their overall huck completion rate under the same team, phase and line scope. The overall rate includes the selected zone and any unmapped releases. Difference is zone rate minus overall rate, displayed in percentage points; no-attempt differences remain undefined. Leaderboard tooltips also show the pooled all-thrower completion rate for that location. These are descriptive comparisons, not disjoint cohorts, causal effects, receiver-adjusted or difficulty-adjusted ratings. Location findings require the selected zone attempt minimum and retain completed/attempted counts.'},
        {'label':'Incoming pass tendencies','componentIds':['ufa-deep-setups','ufa-deep-sequences'],
         'definition':'Classify the verified prior disc-flight vector as forward when dy > abs(dx), backward when -dy > abs(dx), otherwise lateral when distance is nonzero. Thus exact 45-degree boundaries belong to lateral. Missing or ambiguous links, missing prior coordinates and zero-distance passes are unclassified; no dead-disc or cutting-route label is inferred. Within each group, huck choice is huck attempts / non-stall next throws with finite current endpoints, while huck completion is completed hucks / huck attempts. Catches with no recorded next throw are not opportunities in this denominator. All setups pools the same groups, including unclassified. Release-location filtering uses current tx/ty; page team/phase/line filters apply first. Missing current geometry is disclosed and excluded from both rates. Source rows include every scoped next throw and its verified prior pass, deduplicated by event ID. Inspect actions select the exact group and release zone; CSV exports preserve the prior-pass category and original IDs. These are descriptive tendencies, not causal effects or comparisons adjusted for receivers, opponents, pressure or throw distance.'},
        {'label':'Deep thrower sampling uncertainty','componentIds':['ufa-deep-release','ufa-deep-profile','ufa-deep-comparison','ufa-deep-setups'],
         'definition':'Release-zone tooltips report a two-sided 95% Wilson interval for completed / attempted hucks, with z=1.959963984540054. Empty rates are undefined. These binomial intervals do not adjust for dependence between throws, opponents or games and do not establish a causal location effect or statistically significant pairwise differences. Highest-observed-zone summaries rank completion rates and require the selected attempt minimum; ties break by attempts then zone ID. The player minimum affects only the leaderboard; the zone minimum also controls the player profile shading and highest-observed-zone summary.'},
    ]
    labels={item['label'] for item in definitions}
    source['metricDefinitions']=[item for item in source.get('metricDefinitions',[]) if item.get('label') not in labels]+definitions
    for definition in source['metricDefinitions']:
        if definition['label']=='Huck passes':
            definition['componentIds']=list(dict.fromkeys(definition['componentIds']+components))
    method={'language':'text','code':'src/content/dashboard/deep-thrower-model.js: precedingPasses verifies unique consecutive passes within the filtered game/team/quarter/point/possession; buildDeepThrower computes completed-catch locations, matched prior-catch locations, and huck release-zone attempts, completions and Wilson intervals. deepThrowerComparison computes each player and release zone under the same huck and denominator rules; rankDeepThrowers applies total, zone and completion eligibility and orders the selected location. priorPassDirection and buildHuckSetups group all located next throws by incoming disc direction, separating huck choice from completion. selectHucks resolves spatial or setup selections to original hucks; sequenceSource includes their verified original preceding passes once. No archetype clusters or causal effects are fitted.'}
    query['methods']=[item for item in query.get('methods',[]) if not item.get('code','').startswith('src/content/dashboard/deep-thrower-model.js:')]+[method]
    return snapshot

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
    old=load_json(ROOT/'src/data.json')
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
    database=None
    team_names=TEAM_NAMES
    if (ROOT/'data/database-exports/current.json').exists():
        database=load_bundle(ROOT,{pid:row.get('portraitUrl') for pid,row in players.items()})
        schedule=database['schedule'];players=database['players'];team_names=database['teamNames']
        # Retain historical aggregate comparisons only; no cached throw/block row
        # can override the selected database export.
        for gid,payload in database['payloads'].items():
            payload['playerStats']=payloads.get(gid,{}).get('playerStats',[])
        payloads=database['payloads']
    events=[]; games=[]; calls=[]; seen=set(); missing=[]; manifests=[]; validation=[]
    if database:manifests=database['files']
    for game in sorted(schedule,key=lambda g:g['GameID']):
        gid=game['GameID']; phase='Regular season' if game.get('RegularSeasonWeek') is not None and not game.get('PlayoffRound') else 'Playoffs'
        cached=ROOT/'data/raw'/f'{gid}.csv'
        payload=payloads.get(gid)
        if database:
            rows=payload['throws'];origin=next(m['file'] for m in manifests if m['table']=='prod.throws')
        elif payload and payload.get('throws'):
            rows=payload['throws']; origin=f'data/source-api/{gid}.json'
            if not (ROOT/origin).exists():origin='data/source-api/sample-game.json'
        elif cached.exists():
            with cached.open() as h:rows=list(csv.DictReader(h))
            origin=f'data/raw/{gid}.csv'
        else:rows=[];origin=f'data/source-api/{gid}.json'
        games.append({'game':gid,'date':gid[:10],'phase':phase,'home':game['HomeTeamID'],'away':game['AwayTeamID'],
                      'throws':len(rows),'status':game.get('Status'),'homeScore':game.get('HomeScore'),'awayScore':game.get('AwayScore')})
        if not rows:
            missing.append({'game':gid,'phase':phase,'reason':'The database export contains no throws.' if database else 'The public API returned zero throws.'})
            continue
        f=ROOT/origin
        if not database:manifests.append({'file':origin,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'rows':len(rows)})
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
                'line':'O-line' if truth(t.get('o_line')) else 'D-line','quarter':int(float(t['game_quarter'])),
                **({'point':number(t.get('quarter_point')),'possession':number(t.get('possession_num')),
                    'possessionThrow':number(t.get('possession_throw')),'eventSequence':number(t.get('global_event_seq')),
                    'throwDistance':number(t.get('throw_distance')),'throwAngle':number(t.get('throw_angle')),
                    'xDiff':number(t.get('x_diff')),'yDiff':number(t.get('y_diff')),
                    'cp':number(t.get('cp')),'cpoe':number(t.get('cpoe')),'ec':number(t.get('ec')),
                    'sourceInsertedAt':t.get('insert_timestamp') or None} if database else {})})
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
                matches=[t for t in ct if int(float(t['game_quarter']))==int(float(b['game_quarter'])) and
                         int(float(t['quarter_point']))==int(float(b['quarter_point'])) and
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
    for tid,(name,abbrev) in team_names.items():
        reg=[g for g in games if g['phase']=='Regular season' and tid in (g['home'],g['away'])]
        teams.append({'id':tid,'name':name,'abbrev':abbrev,'games':sum(g['throws']>0 for g in reg),
                      'scheduled':len(reg),'missing':', '.join(g['game'] for g in reg if not g['throws'])})
    teams.sort(key=lambda t:t['name'])
    stats={'throwRows':len(events),'regularSeasonThrows':sum(e['phase']=='Regular season' for e in events),
        'gamesWithThrows':sum(g['throws']>0 for g in games),'regularSeasonGames':sum(g['phase']=='Regular season' and g['throws']>0 for g in games),
        'teams':len(teams),'players':len(players),'nullAec':sum(e['aec'] is None for e in events),
        'callahans':len(calls),'missingGames':missing,'unknownPlayerNames':unknown,
        'playerMetricChecks':len(validation),'maxPlayerMetricDelta':max((abs(x['delta']) for x in validation),default=None),
        'metricDisagreements':[x for x in validation if abs(x['delta'])>1e-8],
        'coordinateExtrema':{k:[min(e[k] for e in events),max(e[k] for e in events)] for k in ('tx','ty','rx','ry')}}
    if database:
        stats['databaseImport']=database['audit']
        stats['comparisonBasis']='Historical per-game player aggregates retained from public API responses; not a fresh database aggregate query.'
        previous={row['id']:row for row in old['queries']['events']['rows']}
        comparable=('game','phase','team','thrower','receiver','tx','ty','rx','ry','complete','drop','stall','aec','throwAec','receiveAec','callahan','line','quarter')
        changes=[]
        for row in events:
            before=previous.get(row['id'])
            if before is None:continue
            fields=[key for key in comparable if before.get(key)!=row.get(key) and not (
                isinstance(before.get(key),(int,float)) and isinstance(row.get(key),(int,float)) and
                abs(before[key]-row[key])<1e-12)]
            if fields:changes.append({'id':row['id'],'fields':fields})
        stats['previousSnapshotComparison']={'previousGeneratedAt':old.get('generatedAt'),
            'previousRows':len(previous),'addedIds':sorted(seen-set(previous)),
            'removedIds':sorted(set(previous)-seen),'changedExistingEvents':changes,
            'numericComparisonTolerance':1e-12}
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
          'Original preserves three attacking-end-zone receiving zones, eight main-field throwing zones, and a Callahan bottom panel. Original includes releases at y=100 in the main field and catches/drops at y=100 in the attacking end zone. The Thrower aEC, Receiver aEC, and Overall aEC views cover all 12 zones, including the own end zone (0 <= y < 20); their bands include the lower edge and exclude the upper edge, except y=120 is included. Those views can separately show Callahans in the bottom panel.'],
       'evidenceFlow':[{'title':'Prior possession browser','detail':'Imported the 2026 per-game throw CSV cache from frisbee-analytics/data/raw/shownspace_throws_2026_by_game. Preserved in data/raw.'},
          {'title':'Schedule and names','detail':'GET https://shownspace.com/api/games?year=2026&limit=500 and GET https://shownspace.com/api/leaderboard?season=2026 on September 29, 2026.'},
          {'title':'Supplemental game records','detail':'GET https://shownspace.com/api/games/{GameID} for missing games and games with Callahans. Full returned records and hashes are preserved.'},
          {'title':'Reference','detail':'https://www.instagram.com/p/Danlzl5SoUs/ — Kings of the Field; player boxes, eight throwing zones, three receiving zones, and one defensive Callahan panel.'}],
       'metricDefinitions':[{'label':'Field-zone assignment','definition':'Original preserves three attacking-end-zone receiving zones, eight main-field throwing zones, and a Callahan bottom panel. Original includes releases at y=100 in the main field and catches/drops at y=100 in the attacking end zone. The Thrower aEC, Receiver aEC, and Overall aEC views cover all 12 zones, including the own end zone (0 <= y < 20); their bands include the lower edge and exclude the upper edge, except y=120 is included. Those views can separately show Callahans in the bottom panel.'},
          {'label':'Thrower aEC','definition':'Sum the supplied aEC for completions and non-drop turnovers. A dropped throw contributes zero to the thrower.'},
          {'label':'Receiver aEC','definition':'Sum supplied aEC for completions and drops credited to the named receiver. Untargeted throwaways have no receiver credit.'},
          {'label': 'Overall aEC', 'definition': 'Overall aEC is each player’s thrower aEC plus receiver aEC within the same box. Thrower credit uses the release location; receiver credit uses the catch/drop location. Both roles are ranked together per player, including in the own end zone. This adds player-role credits, not unique possession value.'},
          {'label':'Callahan aEC','definition':'Reconstruction of the reference panel: negate the opposing Callahan throw aEC and assign it to the uniquely matched defender. This is separate from offensive player totals.'},
          {'label':'Completion rate','definition':'Completed throws divided by all throws in the selected player and zone. For receiving: catches divided by catches plus recorded drops.'}]}
    if database:
        metadata.update({'label':'Shown Space · database CSV exports · 2026 UFA',
            'files':[m['file'] for m in manifests],
            'evidenceFlow':[
                {'title':'Database exports','detail':f"User exported prod.throws, prod.games, prod.players, prod.teams and prod.blocks through DBeaver on {database['audit']['snapshot']}. Local copies and SHA-256 hashes are preserved in data/database-exports. No live database query was made during this import."},
                {'title':'Season and identity','detail':'Filter game, roster and team records to 2026. Attach each throw and block to its GameID, then derive its team from the game and is_home_team. Collapse repeated roster identities by PlayerID only after confirming names agree; roster rows never multiply events.'},
                {'title':'Additional source fields','detail':'Preserve point, possession, possession_throw and global_event_seq for future possession work. Preserve supplied throw_angle, throw_distance, x_diff and y_diff for radial plots, and supplied cp, cpoe and ec. No radial bin definitions or new metric models are inferred.'},
                {'title':'Portraits and comparison','detail':'Keep the existing locally stored portraits and cached public API portrait URLs. Historical player aggregates in data/source-api are used only for reconciliation, not as imported event values.'},
                {'title':'Reference','detail':'Shown Space Kings of the Field provides the reconstructed zone layout. Player contribution definitions are unchanged.'}],
            'caveats':[metadata['caveats'][0],
                'The CSV export date is October 12, 2026; this is not a live connection. Counts were checked locally, not against a fresh database COUNT query.',
                'The full local exports contain other seasons; this dashboard deliberately uses only 2026.',
                'Repeated 2026 roster IDs are collapsed into one display identity; one blank roster ID is omitted from the display directory. Active flags are not used to exclude historical passes.',
                'The reference is a July 10 snapshot. These results use a later database export; rankings can differ.',
                *metadata['caveats'][2:]]})
    snapshot={**old,'id':old['id'],'surface':'dashboard','title':old.get('title','UFA player archetyping'),'generatedAt':now,'status':'reviewed','buildStatus':'updating','filters':old.get('filters',[
        {'id':'team','label':'Team','field':'team','defaultValue':'glory','queryIds':['events','callahans']},
        {'id':'phase','label':'Season phase','field':'phase','defaultValue':'Regular season','queryIds':['events','callahans','games']},
        {'id':'line','label':'Line','field':'line','defaultValue':'all','queryIds':['events','callahans']}]),
      'queries':{k:{'rows':rows,'source':deepcopy(metadata),'methods':[{'language':'python','code':'python3 tools/build_dataset.py'}]} for k,rows in
        [('events',events),('callahans',calls),('players',list(players.values())),('teams',teams),('games',games)]}}
    if database:
        tables={'events':['throws','games'],'callahans':['blocks','throws','games'],
                'players':['players'],'teams':['teams','games','throws'],'games':['games','throws']}
        for query,names in tables.items():
            snapshot['queries'][query]['source']['tables']=[f'prod.{name}' for name in names]
            snapshot['queries'][query]['source']['files']=[m['file'] for m in manifests if m['table'] in {f'prod.{name}' for name in names}]
        snapshot['queries']['players']['source']['files']+=['data/source-api/leaderboard.json','data/source-api/*.json','src/content/assets/portraits.json']
    add_connection_metadata(snapshot)
    add_radial_metadata(snapshot)
    add_deep_thrower_metadata(snapshot)
    add_player_profiles(snapshot)
    add_thrower_profiles(snapshot)
    add_offensive_contributions(snapshot)
    (ROOT/'src/data.json').write_text(json.dumps(snapshot,separators=(',',':'),allow_nan=False))
    print(json.dumps(stats,indent=2))

if __name__=='__main__':build()
