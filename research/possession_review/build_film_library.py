"""Prepare a source-backed film-review queue; does not relabel or refit the study."""
from pathlib import Path
import copy
import hashlib
import json
import math
import re

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / 'research/dead_disc_study/raw_events'
CANVAS = ROOT / 'research/previews/UFA-possession-review.canvas.tsx'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def time_label(seconds):
    n = max(0, round(seconds))
    return f'{n//3600}:{n//60%60:02}:{n%60:02}' if n >= 3600 else f'{n//60}:{n%60:02}'


def main():
    manifest = json.loads((HERE / 'film_library_manifest.json').read_text())
    current = json.loads(re.search(r'const DATA = (.*);\n', CANVAS.read_text()).group(1))
    original = [copy.deepcopy(c) for c in current['cases'] if c['id'] in list('ABCDEFGHI')]
    preserved = {}
    for c in original:
        gid = c.get('gameSource', {}).get('game', current['game'])
        key = c.get('possessionId', f"{gid}|{c['sourceSide']}|{c['pointStartIndex']}|{c['ownPossession']}")
        preserved[key] = c
    ppath = ROOT / 'research/oline_possessions/possessions.csv'
    tpath = ROOT / 'research/oline_possessions/throws.csv'
    p = pd.read_csv(ppath)
    t = pd.read_csv(tpath)
    players = pd.read_csv(ROOT / 'data/database-exports/2026-10-12/players.csv')
    names = players[players.Year.eq(2026)].drop_duplicates('PlayerID').set_index('PlayerID').full_name.to_dict()
    receipts = json.loads((RAW / 'source_receipt.json').read_text())
    types = {18:'Complete', 19:'Goal', 20:'Drop', 22:'Throwaway', 23:'Callahan'}
    cases = []
    summaries = []
    raw_evidence = []
    new_number = 0
    for game in manifest['games']:
        gid = game['gameId']
        path = RAW / f'{gid}.json'
        assert sha(path) == receipts[gid]['sha256']
        raw = json.loads(path.read_text())['data']
        point_lookup = {}
        for side in ['home', 'away']:
            es = raw[side + 'Events']
            quarter = 1
            for i, event in enumerate(es):
                if event['type'] in [1, 2]:
                    end = next((j for j in range(i+1, len(es)) if es[j]['type'] in {1,2,28,29,30,31,32,33}), len(es))
                    point_lookup.setdefault((side, quarter, event.get('time')), []).append((i, end))
                if event['type'] in {28,29,30,31,32,33}:
                    quarter = event['type'] - 26
        gp = p[p.GameID.eq(gid) & p.quarter.eq(1)].sort_values(['point_start_time', 'own_possession', 'team'])
        for _, pos in gp.iterrows():
            pid = pos.possession_id
            side = pid.split('|')[1]
            es = raw[side + 'Events']
            point_index = int(pos.point_id.rsplit('|', 1)[1])
            opposite = 'away' if side == 'home' else 'home'
            peer_matches = point_lookup.get((opposite, 1, int(pos.point_start_time)), [])
            peer_range = peer_matches[0] if len(peer_matches) == 1 else None
            peer_events = raw[opposite + 'Events']
            pulls = [] if peer_range is None else [(i, peer_events[i]) for i in range(*peer_range) if peer_events[i]['type'] in [7, 8]]
            pull = pulls[0] if len(pulls) == 1 else None
            rows = t[t.possession_id.eq(pid)].sort_values('ordinal')
            throws = []
            previous = int(pos.start_idx)
            for _, row in rows.iterrows():
                idx = int(row.source_side_idx)
                event = es[idx]
                xy = [float(row[k]) for k in ['tx','ty','rx','ry']]
                expected = [event['throwerX'], event['throwerY'], event.get('receiverX', event.get('turnoverX')), event.get('receiverY', event.get('turnoverY'))]
                assert xy == expected and event['type'] == int(row.source_event_type)
                throws.append({'n':int(row.ordinal), 'from':names.get(row.Thrower, str(row.Thrower)),
                    'to':'Unknown target' if pd.isna(row.Receiver) else names.get(row.Receiver, str(row.Receiver)),
                    'xy':xy, 'outcome':types[event['type']], 'huck':bool(row.huck), 'sourceIndex':idx,
                    'before':[e['type'] for e in es[previous+1:idx]]})
                previous = idx
            assert len(throws) == int(pos.throws)
            own_score = sum(e['type'] in {12,19} for e in es[:point_index])
            other_score = sum(e['type'] in {15,23} for e in es[:point_index])
            quarter_point = sum(e['type'] in {1,2} for e in es[:point_index+1])
            time_left = 720 - int(pos.point_start_time)
            tags = ['After a turnover' if pos.own_possession > 1 else 'Opening possession']
            if throws:
                x,y,rx,ry = throws[0]['xy']
                if x == 0 and y == 40: tags.append('Brick coordinates')
                if abs(x) >= 23: tags.append('Sideline start')
                if throws[0]['huck']: tags.append('First throw goes deep')
                if abs(rx) < abs(x): tags.append('First pass moves inward')
                if rx == x and ry == y: tags.append('Repeated coordinates')
                if throws[0]['outcome'] not in ['Complete', 'Goal']: tags.append('First attempt incomplete')
            else:
                tags.append('No physical throw recorded')
            if pos.has_timeout or pos.has_injury or pos.has_penalty: tags.append('Recorded stoppage')
            event_index = throws[0]['sourceIndex'] if throws else int(pos.start_idx)
            timestamp = es[event_index].get('timestamp')
            time_source = {'side':side, 'eventIndex':event_index, 'kind':'First physical throw' if throws else 'Possession start'}
            if timestamp is None and pos.own_possession == 1 and pull is not None:
                timestamp = pull[1].get('timestamp')
                time_source = {'side':opposite,'eventIndex':pull[0],'kind':'Opposing pull record; opening-throw time is unknown'}
            if timestamp is None and pos.own_possession > 1 and peer_range:
                losses = [(i,peer_events[i]) for i in range(*peer_range) if peer_events[i]['type'] in {20,21,22,24}]
                k = int(pos.own_possession)-2
                if k < len(losses):
                    idx,ev = losses[k]
                    timestamp = ev.get('timestamp')
                    time_source = {'side':opposite,'eventIndex':idx,'kind':'Opposing turnover record; first-throw time is unknown'}
            film = None
            film_unavailable = None
            if timestamp is not None and game.get('anchors'):
                anchors = game['anchors']
                same_side = [a for a in anchors if a['sourceSide'] == time_source['side']]
                anchor = min(same_side or anchors, key=lambda a: abs(timestamp-a['sourceTimestamp']))
                estimate = anchor['videoSeconds'] + timestamp - anchor['sourceTimestamp']
                if 0 <= estimate < game.get('durationSeconds', 20000):
                    film = {'start':time_label(max(0,estimate-60)), 'end':time_label(estimate+35),
                        'score':f"Q1 · {pos.team_name} {own_score}–{other_score} opponent · Team possession {int(pos.own_possession)}",
                        'approximate':True, 'estimatedActionSeconds':round(estimate,1), 'timingSource':time_source,
                        'observation':'Use the score, point-start clock, and first thrower to confirm the correct sequence. The seek window is estimated from recorded timestamps; it has not been individually checked.',
                        'question':'Which recorded throw begins the attack?', 'reviewStatus':'Awaiting film review.'}
                elif estimate < 0:
                    film_unavailable = 'The estimated opening falls before this recording starts. Do not label this opening from this recording; mark it as unavailable or use another recording.'
                else:
                    film_unavailable = 'The estimated opening falls outside this recording. The event-to-video alignment needs checking.'
            original_case = preserved.get(pid)
            if original_case:
                case = copy.deepcopy(original_case)
                if not case.get('film') and film: case['film'] = film
            else:
                new_number += 1
                case = {'id':f'R{new_number:03}', 'title':f"{pos.team_name} · point {quarter_point} · possession {int(pos.own_possession)}",
                    'team':pos.team_name, 'quarter':1,'point':quarter_point,'ownPossession':int(pos.own_possession),
                    'sourceSide':side,'pointStartIndex':point_index,'start':'After a turnover in the same receiving point' if pos.own_possession>1 else 'Opening receiving possession',
                    'prompt':'Review the opening action before choosing a label. Short or inward movement alone does not establish setup.',
                    'sourceCue':f'Q1 · point begins {time_label(time_left)} · score {own_score}–{other_score} from the receiving team’s perspective',
                    'throws':throws,'film':film}
            case.update({'possessionId':pid,'libraryGroup':game['group'],'libraryTags':tags,
                'pointClock':time_label(time_left),'scoreLabel':f"{pos.team_name} {own_score}–{other_score} opponent",
                'possessionOutcome':str(pos.outcome),'sourceEndType':int(pos.end_type),
                'librarySelection':'Every validated first-quarter possession in the selected game; not selected by huck or scoring outcome.',
                'timestampEvidence':{'timestamp':timestamp,**time_source},
                'filmUnavailable':film_unavailable,
                'pullEvidence':None if pull is None else {'sourceSide':opposite,'sourceIndex':pull[0],**pull[1]},
                'recordedStoppage':bool(pos.has_timeout or pos.has_injury or pos.has_penalty),
                'gameSource':{'game':gid,'label':f"{game['title']} · {gid[:10]}",'url':f'https://shownspace.com/game-center/{gid}',
                    'source':'Preserved ShownSpace export and UFA event capture. Geometry is recorded data; setup labels require film review.',
                    'rawSha256':sha(path),'rawReceipt':receipts[gid]},
                'filmSource':{'url':game['url'],'title':game['title'],'coverageNote':game.get('coverageNote'),'reviewMethod':'Recording access and selected alignment frames checked. Most individual windows remain unreviewed.',
                    'timeNote':'Approximate windows come from event timestamps and may need adjustment. Confirm the score and first thrower before labeling.'}})
            if original_case:
                assert case['throws'] == original_case['throws']
            cases.append(case)
        summaries.append({'gameId':gid,'title':game['title'],'url':game['url'],'group':game['group'],
                          'possessions':len(gp),'teams':sorted(gp.team_name.unique().tolist()),'recordingStatus':game['recordingStatus']})
        raw_evidence.append({'gameId':gid,'sha256':sha(path),'receipt':receipts[gid]})
    selected_ids = {c['possessionId'] for c in cases}
    for pid, case in preserved.items():
        if pid not in selected_ids:
            case.update({'possessionId':pid,'libraryGroup':'Earlier examples','libraryTags':['Earlier reviewed example'],
                         'librarySelection':'Earlier deliberately selected example, outside the consecutive first-quarter batch.'})
            cases.append(case)
    assert len({c['possessionId'] for c in cases}) == len(cases)
    library = {'createdOn':'2026-11-11','title':'Opening throws: large film review',
        'selection':'All validated first-quarter receiving-team possessions in twelve purposefully selected games covering the twenty-two teams in the preserved study export. Earlier A–I examples are retained. This is not a league-random sample.',
        'scopeLimit':'The definition can be explored here; classification accuracy has not been measured. Later-quarter openings and other games remain outside the consecutive batch.',
        'workingSetupDefinition':current['workingSetupDefinition'],'games':summaries,'cases':cases,
        'counts':{'firstQuarterPossessions':sum(g['possessions'] for g in summaries),'totalCases':len(cases),
            'teams':len({c['team'] for c in cases}),'games':len(summaries),
            'subsequentFirstQuarter':sum(c['ownPossession']>1 and c.get('libraryGroup')!='Earlier examples' for c in cases),
            'outsideRecording':sum(bool(c.get('filmUnavailable')) for c in cases)},
        'sourceInputs':{'possessionsSha256':sha(ppath),'throwsSha256':sha(tpath),'rawGames':raw_evidence},
        'timingCaution':'Event timestamps are operator records, not video timestamps. Estimated seek windows are navigation aids, not verified clip boundaries. Match the scoreboard and participants; flag mismatches.',
        'simplerRoute':'Use the event stream to locate starts and distinguish initial from subsequent possessions. Test any setup rule derived from start context and throw geometry against film labels on reserved games before applying it elsewhere.'}
    (HERE/'film_library.json').write_text(json.dumps(library,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(library['counts']))


if __name__ == '__main__':
    main()
